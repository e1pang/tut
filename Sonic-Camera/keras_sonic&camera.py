'''

pilots.py

Methods to create, use, save and load pilots. Pilots 
contain the highlevel logic used to determine the angle
and throttle of a vehicle. Pilots can include one or more 
models to help direct the vehicles motion. 

'''




import os
import numpy as np
import keras
from ... import utils


import donkeycar as dk
from donkeycar import utils

class KerasPilot():
 
    def load(self, model_path):
        self.model = keras.models.load_model(model_path)
    
    
    def train(self, train_gen, val_gen, 
              saved_model_path, epochs=100, steps=100, train_split=0.8):
        
        """
        train_gen: generator that yields an array of images an array of 
        
        """

        #checkpoint to save model after each epoch
        save_best = keras.callbacks.ModelCheckpoint(saved_model_path, 
                                                    monitor='val_loss', 
                                                    verbose=1, 
                                                    save_best_only=True, 
                                                    mode='min')
        
        #stop training if the validation error stops improving.
        early_stop = keras.callbacks.EarlyStopping(monitor='val_loss', 
                                                   min_delta=.0005, 
                                                   patience=5, 
                                                   verbose=1, 
                                                   mode='auto')
        
        callbacks_list = [save_best, early_stop]
        
        hist = self.model.fit_generator(
                        train_gen, 
                        steps_per_epoch=steps, 
                        epochs=epochs, 
                        verbose=1, 
                        validation_data=val_gen,
                        callbacks=callbacks_list, 
                        validation_steps=steps*(1.0 - train_split))
        return hist


class KerasCategorical(KerasPilot):
    def __init__(self, model=None, *args, **kwargs):
        super(KerasCategorical, self).__init__(*args, **kwargs)
        if model:
            self.model = model
        else:
            self.model = default_categorical()
        
    def run(self, img_arr, son_arr): ##@@## take sonic data as 'son_arr'
        img_arr = img_arr.reshape((1,) + img_arr.shape)
        son_arr=  np.array(son_arr).reshape(1,3)  ##@@## 
        angle_binned, throttle = self.model.predict([img_arr, son_arr]) ##@@## put son_arr into model
        #angle_certainty = max(angle_binned[0])
        angle_unbinned = utils.linear_unbin(angle_binned)
        return angle_unbinned, throttle[0][0]
    

    

def default_categorical():
    from keras.layers import Input, Dense, merge
    from keras.models import Model
    from keras.layers.merge import concatenate
    from keras.layers import Convolution2D, MaxPooling2D, Reshape, BatchNormalization
    from keras.layers import Activation, Dropout, Flatten, Dense, Cropping2D, Lambda

    img_in = Input(shape=(120, 160, 3), name='img_in')                      # First layer, input layer, Shape comes from camera.py resolution, RGB
    son_arr  = Input(shape=(3,), name='son_arr') ##@@## specify input and its shape
   
    x = img_in
    x = Convolution2D(24, (5,5), strides=(2,2), activation='relu')(x)       # 24 features, 5 pixel x 5 pixel kernel (convolution, feauture) window, 2wx2h stride, relu activation
    x = Convolution2D(32, (5,5), strides=(2,2), activation='relu')(x)       # 32 features, 5px5p kernel window, 2wx2h stride, relu activation
    x = Convolution2D(64, (5,5), strides=(2,2), activation='relu')(x)       # 64 features, 5px5p kernal window, 2wx2h stride, relu
    x = Convolution2D(64, (3,3), strides=(2,2), activation='relu')(x)       # 64 features, 3px3p kernal window, 2wx2h stride, relu
    x = Convolution2D(64, (3,3), strides=(1,1), activation='relu')(x)       # 64 features, 3px3p kernal window, 1wx1h stride, relu

    # Possibly add MaxPooling (will make it less sensitive to position in image).  Camera angle fixed, so may not to be needed

    x = Flatten(name='flattenedx')(x)                                        # Flatten to 1D (Fully connected)
    x= Dense(100, activation='relu')(x)
    x=Dropout(.1)(x)

    y=son_arr ##@@## here is where you throw in sonic data
    y = Dense(6, activation= 'relu')(y)
    y = Dense(6, activation= 'relu')(y)   ##@@## why three layers and six nodes? it just worked
    y = Dense(6, activation= 'relu')(y)   ##@@## it could've probably be done with one layer and fewer nodes since our sonic data was so simple

    x = concatenate([x, y])  ##@@##combine image and sonic for two more layers
    x = Dense(50, activation='relu')(x)                                    # Classify the data into 100 features, make all negatives 0
    x = Dropout(.1)(x)                                                      # Randomly drop out (turn off) 10% of the neurons (Prevent overfitting)
    x = Dense(50, activation='relu')(x)                                     # Classify the data into 50 features, make all negatives 0
    x = Dropout(.1)(x)                                                      # Randomly drop out 10% of the neurons (Prevent overfitting)

    #categorical output of the angle
    angle_out = Dense(15, activation='softmax', name='angle_out')(x)        # Connect every input with every output and output 15 hidden units. Use Softmax to give percentage. 15 categories and find best one based off percentage 0.0-1.0

    #continous output of throttle
    throttle_out = Dense(1, activation='relu', name='throttle_out')(x)      # Reduce to 1 number, Positive number only

    model = Model(inputs=[img_in, son_arr], outputs=[angle_out, throttle_out])
    model.compile(optimizer='rmsprop',
                  loss={'angle_out': 'categorical_crossentropy',
                        'throttle_out': 'mean_absolute_error'},
                  loss_weights={'angle_out': 0.9, 'throttle_out': .001})

    return model

