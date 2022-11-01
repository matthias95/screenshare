from pynput import keyboard
from mss import mss
import cv2
import numpy as np
import argparse
import socket


from ._version import __version__

DEFAUL_PORT = 8000

def main():

    parser = argparse.ArgumentParser(description='Stream your screen to ')
    
    parser.add_argument('--host', type=str, help='IP or hostname which acts as display server' )
    parser.add_argument('--port', type=int, default=DEFAUL_PORT, help='Port of the display server')
    parser.add_argument('--compression', choices=['jpg', 'png'], default='jpg', help='Image compression used for streaming')

    parser.add_argument('--scale', type=float, default=None, help='Resolution scaling')

    args = parser.parse_args()
    

    if args.host is None:
        hostname = socket.gethostname()   

        ip = hostname
        try:
            ip = socket.gethostbyname(hostname)   
        except Exception as ex:
            pass

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception as ex:
            pass
        
        cmd = 'screenshare'
        cmd += ' --host {ip}'
        if args.port != DEFAUL_PORT:
            cmd += f' --port {args.port}'
        
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('0.0.0.0', args.port))

        sock.listen(0)
        sock.settimeout(1)

        
        print('This is the Display Server')
        print('Launch one of the following cmd lines to start streaming to this machine:')
        print(cmd.format(ip=hostname))
        print(cmd.format(ip=ip))
        

        def read_n_bytes(connection, n):
            res = bytes()
            while len(res) < n:
                tmp = connection.recv(min(2**12, n))
                res += tmp
                if len(tmp) == 0:
                    raise IOError('Connection closed')
            return res

        fullscreen = True
        while True:
            try:
                connection, client_address = sock.accept()
                connection.settimeout(1)
                num_img_bytes = np.frombuffer(read_n_bytes(connection, 4), np.int32)[0]
                
                data = read_n_bytes(connection, num_img_bytes)
                
                
                img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                
                cv2.namedWindow('window', cv2.WINDOW_NORMAL )

                if fullscreen:
                    cv2.setWindowProperty('window', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                else:
                    cv2.setWindowProperty('window', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                
                cv2.imshow('window', img)
                if cv2.waitKey(16) & 0xFF == ord('m'):
                    fullscreen = not fullscreen
                    
            except KeyboardInterrupt as ex:
                cv2.destroyAllWindows()
                exit()
            except socket.timeout as ex:
                cv2.destroyAllWindows()
            except Exception as ex:
                cv2.destroyAllWindows()
                print(ex)
    else:

        def send_bytes(bytes_array, ip, port):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            sock.connect((ip, port))
            
            sock.sendall(bytes_array)
            sock.close()
            
        def img_to_bytes(img):
            res, bytes_array = cv2.imencode(f'.{args.compression}', img,  [cv2.IMWRITE_PNG_COMPRESSION, 1, cv2.IMWRITE_JPEG_QUALITY, 80, cv2.IMWRITE_JPEG_PROGRESSIVE, 1, cv2.IMWRITE_JPEG_OPTIMIZE, 1])
            return bytes_array.tobytes()

        class KeyboardState:
            def __init__(self):
                self.selected_monitor_idx = -1
                self.pressed_keys = set()
        
        keyboard_state = KeyboardState()

        digit_keys = [keyboard.KeyCode(char=str(i)) for i in range(10)]
        f_keys = [keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12]
        hotkeys = {key:idx for idx, key in sum([list(enumerate(keys)) for keys in [digit_keys, f_keys]], [])} 

        def on_press(key):
            keyboard_state.pressed_keys.add(key)
            if keyboard.Key.alt_l in keyboard_state.pressed_keys and key in hotkeys:
                selected_monitor_idx = hotkeys[key]
                if selected_monitor_idx != keyboard_state.selected_monitor_idx:
                    keyboard_state.selected_monitor_idx = selected_monitor_idx
                    print('Start streaming')
                else:
                    keyboard_state.selected_monitor_idx = -1
                    print('Stop streaming')

        def on_release(key):
            if key in keyboard_state.pressed_keys:
                keyboard_state.pressed_keys.remove(key)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        host = socket.gethostbyname(args.host)
        print('This is the Streaming Server')
        print('Press alt + [F9-F12] to toggle streaming your screens')


        class ROISelectorState:
            def __init__(self):
                self.p1 = None
                self.p2 = None
                self.is_moving = False

        roi_selector_state = ROISelectorState()

        def on_mouse(event, x, y, flags, userdata):
            if event == cv2.EVENT_LBUTTONDOWN:
                roi_selector_state.p1 = (x,y)
                roi_selector_state.is_moving = True
                    
            elif event == cv2.EVENT_MOUSEMOVE and roi_selector_state.is_moving:
                roi_selector_state.p2 = (x,y)
            elif event == cv2.EVENT_LBUTTONUP:
                roi_selector_state.p2 = (x,y)
                roi_selector_state.is_moving = False
                
            if event == cv2.EVENT_RBUTTONUP:
                roi_selector_state.p1, roi_selector_state.p2 = None, None
                roi_selector_state.is_moving = False

        with mss() as sct:
            while True:
                try:
                    if keyboard_state.selected_monitor_idx >= 0 and keyboard_state.selected_monitor_idx < len(sct.monitors):
                        
                        screen_shot = sct.grab(sct.monitors[keyboard_state.selected_monitor_idx])

                        img = np.uint8(screen_shot)[...,:3].copy()
                        
                        if args.scale is not None:
                            scale = args.scale 
                        else:
                            scale = 1080 / img.shape[0]

                        
                        
                        if roi_selector_state.p1 is not None and roi_selector_state.p2 is not None:
                            x_min = np.clip(min(roi_selector_state.p1[0], roi_selector_state.p2[0]), 0, img.shape[1])
                            y_min = np.clip(min(roi_selector_state.p1[1], roi_selector_state.p2[1]), 0, img.shape[0])
                            x_max = np.clip(max(roi_selector_state.p1[0], roi_selector_state.p2[0]), 0, img.shape[1])
                            y_max = np.clip(max(roi_selector_state.p1[1], roi_selector_state.p2[1]), 0, img.shape[0])
                            
                            if (x_max - x_min) < 10:
                                x_max += 10 - (x_max - x_min)
                            if (y_max - y_min) < 10:
                                y_max += 10 - (y_max - y_min)
                            img_roi = img[y_min:y_max+1, x_min:x_max+1].copy()

                            img = cv2.rectangle(img.copy(), roi_selector_state.p1, roi_selector_state.p2, 255, 2)

                        else:
                            img_roi = img
                        
                        img_resized = cv2.resize(img_roi, (0,0), fx=scale, fy=scale)

                        bytes_array = img_to_bytes(img_resized)
                        
                        send_bytes(np.int32(len(bytes_array)).tobytes() + bytes_array, ip=host, port=args.port)
                        
                        cv2.namedWindow('select_roi', cv2.WINDOW_NORMAL)
                        cv2.setMouseCallback('select_roi', on_mouse)
                        cv2.imshow('select_roi', img)
                        cv2.waitKey(10)
                    else:
                        cv2.destroyAllWindows()
                except KeyboardInterrupt as ex:
                    exit()
                except socket.timeout as ex:
                    cv2.destroyAllWindows()
                except Exception as ex:
                    cv2.destroyAllWindows()
                    print(ex)
            

                    
