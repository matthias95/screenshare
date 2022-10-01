from pynput import keyboard
from mss import mss
import cv2
import numpy as np

import argparse
import socket
import time

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
        ip = socket.gethostbyname(hostname)   
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
        
        def on_press(key):
            keyboard_state.pressed_keys.add(key)
            if keyboard.Key.alt_l in keyboard_state.pressed_keys and key in f_keys:
                selected_monitor_idx = f_keys.index(key)
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

        with mss() as sct:
            while True:
                try:
                    if keyboard_state.selected_monitor_idx >= 0 and keyboard_state.selected_monitor_idx < len(sct.monitors):
                        
                        screen_shot = sct.grab(sct.monitors[keyboard_state.selected_monitor_idx])

                        img = np.uint8(screen_shot)[...,:3]
                        
                        if args.scale is not None:
                            scale = args.scale 
                        else:
                            scale = 1080 / img.shape[0]

                        img = cv2.resize(img, (0,0), fx=scale, fy=scale)
                        
                        bytes_array = img_to_bytes(img)
                        
                        send_bytes(np.int32(len(bytes_array)).tobytes() + bytes_array, ip=host, port=args.port)
                        
                        time.sleep(1/60)
                except KeyboardInterrupt as ex:
                    exit()
                except socket.timeout as ex:
                    pass
                except Exception as ex:
                    print(ex)
                    
                    
