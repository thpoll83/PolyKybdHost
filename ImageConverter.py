import sys
import imageio.v3 as iio
import numpy as np
#from matplotlib import pyplot as plt

class ImageConverter:
    def __init__(self, filename):
        im = iio.imread(filename)
        #convert the image to b/w
        self.image = np.array(np.dot(im[...,:3], [0.2989/255, 0.5870/255, 0.1140/255]), dtype=bool)
        self.h, self.w = self.image.shape
        #plt.imshow(self.image)
        #plt.show()
        self.overlays = {}
        print(f"Loaded {filename}: {self.w}x{self.h}")
        
    def extract_overlays(self):
        #we expect 10x9 images each having 72x40px
        if self.w >= 72*10 and self.h >= 40*9:
            keycode = 4 #KC_A
            for y in range (0, 9):
                for x in range (0, 10):
                    topx = x*72
                    topy = y*40
                    bottomx = (x+1)*72-1
                    bottomy =  (y+1)*40-1
                    slice = self.image[topy:bottomy, topx:bottomx]
                    if slice.any():
                        self.overlays[keycode] = np.packbits(slice, axis=None).tobytes()
                        #plt.imshow(slice)
                        #plt.show()
                        
                    keycode = keycode + 1
                    if keycode == 84: #skip keypad keycodes
                        keycode = 100 # KC_NONUS_BACKSLASH
                    if keycode == 102: #skip media keys etc.
                        keycode = 224 # KC_LEFT_CTRL
            return self.overlays
        else:
            print("Image too small")
            return None
                
        