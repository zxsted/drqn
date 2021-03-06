import numpy as np
import tensorflow as tf
import tensorflow.contrib.slim as slim


class Qnetwork():
    def __init__(self, h_size, a_size, rnn_cell, scopeName, discount=0.99, **kwargs):
        self.h_size, self.a_size, self.discount = h_size, a_size, discount
        self.scalarInput = tf.placeholder(shape=[None, 7056], dtype=tf.uint8)
        self.batch_size = tf.placeholder(dtype=tf.int32, shape=[])
        self.trainLength = tf.placeholder(dtype=tf.int32, shape=[])

        self.frames = tf.reshape(self.scalarInput/255, [-1, 1, 84, 84])
        self.conv1 = slim.convolution2d(
            inputs=self.frames, num_outputs=32,
            kernel_size=(8, 8), stride=(4, 4), padding='VALID',
            data_format='NCHW',
            biases_initializer=None, scope=scopeName+'_conv1'
        )
        self.conv2 = slim.convolution2d(
            inputs=self.conv1, num_outputs=64,
            kernel_size=(4, 4), stride=(2, 2), padding='VALID',
            data_format='NCHW',
            biases_initializer=None, scope=scopeName+'_conv2'
        )
        self.conv3 = slim.convolution2d(
            inputs=self.conv2, num_outputs=64,
            kernel_size=(3, 3), stride=(1, 1), padding='VALID',
            data_format='NCHW',
            biases_initializer=None, scope=scopeName+'_conv3'
        )
        self.conv4 = slim.convolution2d(
            inputs=self.conv3, num_outputs=h_size,
            kernel_size=(7, 7), stride=(1, 1), padding='VALID',
            data_format='NCHW',
            biases_initializer=None, scope=scopeName+'_conv4'
        )

        self.convFlat = tf.reshape(
            slim.flatten(self.conv4), [self.batch_size, self.trainLength, h_size])

        self.state_init = rnn_cell.zero_state(self.batch_size, tf.float32)
        self.rnn, self.rnn_state = tf.nn.dynamic_rnn(
            inputs=self.convFlat, cell=rnn_cell, dtype=tf.float32,
            initial_state=self.state_init, scope=scopeName+'_rnn'
        )
        self.rnn = tf.reshape(self.rnn, shape=[-1, h_size])

        self.streamA, self.streamV = tf.split(self.rnn, 2, axis=1)

        xavier_init = tf.contrib.layers.xavier_initializer()
        self.AW = tf.Variable(xavier_init([h_size//2, a_size]))
        self.VW = tf.Variable(xavier_init([h_size//2, 1]))
        self.A = tf.matmul(self.streamA, self.AW)
        self.V = tf.matmul(self.streamV, self.VW)

        self.Qout = self.V + \
            (self.A - tf.reduce_mean(self.A, axis=1, keepdims=True))
        self.predict = tf.argmax(self.Qout, 1)
        self.action = self.predict[-1]

        self.sample_terminals = tf.placeholder(tf.int32, shape=[None], name='sample_terminals')
        end_multiplier = tf.cast(- (self.sample_terminals - 1), tf.float32)

        self.sample_rewards = tf.placeholder(tf.float32, shape=[None], name='sample_rewards')
        self.doubleQ = tf.placeholder(tf.float32, shape=(None), name='doubleQ')
        
        self.targetQ = self.sample_rewards + self.discount * self.doubleQ * end_multiplier
        
        self.actions = tf.placeholder(shape=[None], dtype=tf.int32)
        self.actions_onehot = tf.one_hot(
            self.actions, a_size, dtype=tf.float32)

        self.Q = tf.reduce_sum(self.Qout * self.actions_onehot,
                               reduction_indices=1)

        # only train on first half of every trace per Lample & Chatlot 2016
        self.mask = tf.concat((tf.zeros((self.batch_size, self.trainLength//2)),
                               tf.ones((self.batch_size, self.trainLength//2))), 1)
        self.mask = tf.reshape(self.mask, [-1])

        self.loss = tf.losses.huber_loss(
            self.Q * self.mask, self.targetQ * self.mask)

        if scopeName == 'main':
            tf.summary.scalar('loss', self.loss)
            tf.summary.histogram('Q', self.Qout)
            tf.summary.histogram('hidden', self.rnn_state)

        self.trainer = tf.train.RMSPropOptimizer(
            0.00025, momentum=0.95, epsilon=0.01)
        self.updateModel = self.trainer.minimize(self.loss)

    def get_action_and_next_state(self, sess, state, frames):
        state = state or (np.zeros((1, self.h_size)),) * 2
        return sess.run([self.action, self.rnn_state], feed_dict={
            self.scalarInput: np.vstack(np.array(frames)),
            self.trainLength: len(frames),
            self.state_init: state,
            self.batch_size: 1
        })

if __name__ == '__main__':
    q = Qnetwork(512, 4, 256, tf.nn.rnn_cell.LSTMCell(num_units=512), 'main')