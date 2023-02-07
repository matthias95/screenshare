from pynput import keyboard, mouse
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
    parser.add_argument('--hide_cursor', action='store_true')

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
        last_frame_timestamp = time.time()
        while True:
            try:
                connection, client_address = sock.accept()
                
                connection.settimeout(1)
                num_img_bytes = np.frombuffer(read_n_bytes(connection, 4), np.int32)[0]
                
                data = read_n_bytes(connection, num_img_bytes)
                
                
                img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                
                cv2.namedWindow('window', cv2.WINDOW_NORMAL)

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
                if (time.time() - last_frame_timestamp) >= 5:
                    cv2.destroyAllWindows()
                print(ex)
            else:
                last_frame_timestamp = time.time()
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
                self._selected_monitor_idx = -1
                self._pressed_keys = set()

                digit_keys = [keyboard.KeyCode(char=str(i)) for i in range(10)]
                f_keys = [keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12]
                self._hotkeys = {key:idx for idx, key in sum([list(enumerate(keys)) for keys in [digit_keys, f_keys]], [])} 

            def on_press(self, key):
                self._pressed_keys.add(key)
                if keyboard.Key.alt_l in self._pressed_keys and key in self._hotkeys:
                    selected_monitor_idx = self._hotkeys[key]
                    if selected_monitor_idx != self._selected_monitor_idx:
                        self._selected_monitor_idx = selected_monitor_idx
                        print('Start streaming')
                    else:
                        self._selected_monitor_idx = -1
                        print('Stop streaming')

            def on_release(self, key):
                if key in self._pressed_keys:
                    self._pressed_keys.remove(key)

            @property
            def selected_monitor_idx(self):
                return self._selected_monitor_idx

        keyboard_state = KeyboardState()

        keyboard_listener = keyboard.Listener(on_press=keyboard_state.on_press, on_release=keyboard_state.on_release)
        keyboard_listener.start()
        

        class MouseState:
            def __init__(self):
                self._x = -1
                self._y = -1

            def on_move(self, x, y):
                self._x = x
                self._y = y

            @property
            def x(self):
                return self._x

            @property
            def y(self):
                return self._y

        
        mouse_state = MouseState()
        mouse_listener = mouse.Listener(on_move=mouse_state.on_move)
        mouse_listener.start()


        host = socket.gethostbyname(args.host)
        print('This is the Streaming Server')
        print('Press alt + [F9-F12] to toggle streaming your screens')


        class ROISelector:
            def __init__(self):
                self._p1 = None
                self._p2 = None
                self._is_moving = False
                self.force_aspect_ratio = False

            def clear_roi(self):
                self._p1, self._p2 = None, None
                self._is_moving = False

            def on_mouse(self, event, x, y, flags, userdata):
                if event == cv2.EVENT_LBUTTONDOWN:
                    self._p1 = (x,y)
                    self._is_moving = True
                    self.force_aspect_ratio = False
                    if flags == (cv2.EVENT_FLAG_LBUTTON + cv2.EVENT_FLAG_SHIFTKEY):
                        self.force_aspect_ratio = True
                        self.aspect_ratio = (16, 9)
                    elif flags == (cv2.EVENT_FLAG_LBUTTON + cv2.EVENT_FLAG_ALTKEY):
                        self.force_aspect_ratio = True
                        self.aspect_ratio = (4, 3)
                elif event == cv2.EVENT_MOUSEMOVE and self._is_moving:
                    self._p2 = (x,y)

                    if self.force_aspect_ratio:
                        self.clip_to_aspect_ratio()
                elif event == cv2.EVENT_LBUTTONUP:
                    self._p2 = (x,y)
                    if self.force_aspect_ratio:
                        self.clip_to_aspect_ratio()
                    self._is_moving = False
                elif event == cv2.EVENT_RBUTTONUP:
                    self.clear_roi()

            def clip_to_aspect_ratio(self):
                w_a, h_a = self.aspect_ratio
                h = self.y_max - self.y_min
                w = self.x_max - self.x_min
                if w == 0 or h == 0:
                    return

                if (w / h) < (w_a / h_a):
                    w = (w // w_a) * w_a
                    h = (w // w_a) * h_a
                else: 
                    h = (h // h_a) * h_a
                    w = (h // h_a) * w_a

                x, y = self.p1
                x2, y2 = self.p2

                if x > x2:
                    w = -w
                if y > y2:
                    h = -h

                self._p2 = (x + w, y + h)

            @property
            def has_roi(self):
                return (self.p1 is not None) and (self.p2 is not None)

            @property
            def x_min(self):
                return max(min(self.p1[0], roi_selector.p2[0]),0)

            @property
            def y_min(self):
                return max(min(roi_selector.p1[1], roi_selector.p2[1]), 0)

            @property
            def x_max(self):
                return max(max(roi_selector.p1[0], roi_selector.p2[0]), 0)
            
            @property
            def y_max(self):
                return max(max(roi_selector.p1[1], roi_selector.p2[1]), 0)

            @property
            def p1(self):
                return self._p1

            @property
            def p2(self):
                return self._p2

        roi_selector = ROISelector()

        last_frame_timestamp = time.time()

        with mss() as sct:
            while True:
                try:
                    if keyboard_state.selected_monitor_idx >= 0 and keyboard_state.selected_monitor_idx < len(sct.monitors):
                        
                        selected_monitor = sct.monitors[keyboard_state.selected_monitor_idx]
                        screen_shot = sct.grab(selected_monitor)
                        
                        img = np.uint8(screen_shot)[...,:3].copy()
                        
                        if not args.hide_cursor:
                            mouse_x = mouse_state.x - selected_monitor['left']
                            mouse_y = mouse_state.y - selected_monitor['top']

                            if mouse_x >= 0 and mouse_x < img.shape[1] and mouse_y >= 0 and mouse_y <= img.shape[0]:
                                color = img[mouse_y, mouse_x]
                                luminance = (0.299 * color[2] + 0.587 * color[1] + 0.114 * color[0])/255
                                if luminance < 0.5:
                                    arrow_color = (255,255,255)
                                    border_color = (0,0,0)
                                else:
                                    arrow_color = (0,0,0)
                                    border_color = (255,255,255)


                                cv2.arrowedLine(img, (mouse_x+50, mouse_y+50), (mouse_x, mouse_y), border_color, 8, line_type=cv2.LINE_AA, tipLength=0.4)
                                cv2.arrowedLine(img, (mouse_x+50, mouse_y+50), (mouse_x, mouse_y), arrow_color, 4, line_type=cv2.LINE_AA, tipLength=0.4)

                        if roi_selector.has_roi:
                            x_min = roi_selector.x_min
                            y_min = roi_selector.y_min
                            x_max = roi_selector.x_max
                            y_max = roi_selector.y_max
                            
                            if (x_max - x_min) < 10:
                                x_max += 10 - (x_max - x_min)
                            if (y_max - y_min) < 10:
                                y_max += 10 - (y_max - y_min)
                            img_roi = img[y_min:y_max+1, x_min:x_max+1].copy()

                            img = cv2.rectangle(img, roi_selector.p1, roi_selector.p2, (0,255,0), 15)

                        else:
                            img_roi = img

                        if args.scale is not None:
                            scale = args.scale 
                        else:
                            scale = 1080 / img.shape[0]

                        img_resized = cv2.resize(img_roi, (0,0), fx=scale, fy=scale)

                        bytes_array = img_to_bytes(img_resized)
                        
                        send_bytes(np.int32(len(bytes_array)).tobytes() + bytes_array, ip=host, port=args.port)
                        
                        cv2.namedWindow('select_roi', cv2.WINDOW_GUI_NORMAL)
                        cv2.setMouseCallback('select_roi', roi_selector.on_mouse)
                        cv2.imshow('select_roi', img)
                        key = cv2.waitKey(10)
                        if key == 27: # ESC key
                            roi_selector.clear_roi()

                        last_frame_timestamp = time.time()
                    else:
                        cv2.destroyAllWindows()
                except KeyboardInterrupt as ex:
                    exit()
                except socket.timeout as ex:
                    if (time.time() - last_frame_timestamp) > 5:
                        cv2.destroyAllWindows()
                    print('socket timeout')
                except Exception as ex:
                    if (time.time() - last_frame_timestamp) > 5:
                        cv2.destroyAllWindows()
                    print(ex)

            
