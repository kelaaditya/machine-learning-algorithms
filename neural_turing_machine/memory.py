import numpy as np
import tensorflow as tf


class Memory:
    def __init__(self,
                 num_memory_vectors=128,
                 size_memory_vector=20,
                 num_read_heads=1,
                 num_write_heads=1,
                 batch_size=1
                ):
        # num_memory_vectors is 'N' from the paper
        self.num_memory_vectors = num_memory_vectors
        
        # size_memory_vector is 'M' from the paper
        self.size_memory_vector = size_memory_vector
        
        # number of read heads of the controller
        self.num_read_heads = num_read_heads
        
        # number of write heads of the controller
        self.num_write_heads = num_write_heads
        
        self.batch_size = batch_size
        
        
    def content_addressing(self, memory, read_and_write_key_vectors, read_and_write_strengths):
        """content-based addressing from memory
        
        num_total_keys == num_read_and_write_heads
        
        Parameters:
        -----------
        
        memory: tf.Tensor 
            shape: (batch_size, num_memory_vectors, size_memory_vector)
            the memory matrix
        read_and_write_key_vectors: tf.Tensor
            shape: (batch_size, size_memory_vector, num_read_and_write_heads)
            concatenated read and write key vectors
        read_and_write_strengths: tf.Tensor
            shape: (batch_size, num_read_and_write_heads)
            tensor of read and write strengths
            
        Returns:
        --------
        tf.Tensor
            shape: (batch_size, num_memory_vectors, num_read_and_write_heads)
        """
        normalized_memory = tf.nn.l2_normalize(memory, axis=2)
        
        normalized_read_and_write_key_vectors = tf.nn.l2_normalize(read_and_write_key_vectors, axis=1)
        
        conv_matrix = tf.matmul(normalized_memory, normalized_read_and_write_key_vectors)
        
        read_and_write_strengths = tf.expand_dims(read_and_write_strengths, 1)
        
        # multiply instead of matmul as each strength gets multiplied
        # with each similarity vector to get out a num_total_key
        # number of addresses
        return tf.nn.softmax(conv_matrix * read_and_write_strengths, axis=1)
        
    
    def interpolation(self,
                      read_and_write_interpolation_gates,
                      read_and_write_prev_weights,
                      content_addressing_weights):
        """interpolates content_addressing with previous weightings
        using the interpolation gates
        
        num_total_gates == num_read_and_write_heads == num_total_keys
        
        Parameters:
        -----------
        read_and_write_interpolation_gates: tf.Tensor
            shape: (batch_size, num_read_and_write_heads)
        read_and_write_prev_weights: tf.Tensor
            shape: (batch_size, num_memory_vectors, num_read_and_write_heads)
        content_addressing_weights: tf.Tensor
            shape: (batch_size, num_memory_vectors, num_read_and_write_heads)
        """
        
        read_and_write_interpolation_gates = tf.expand_dims(read_and_write_interpolation_gates, 1)
        
        gated_weightings = read_and_write_interpolation_gates * content_addressing_weights + \
                           (1 - read_and_write_interpolation_gates) * read_and_write_prev_weights
        
        return gated_weightings
        
        
    def convolutional_shift(self, gated_weightings, shift_weightings, read_and_write_gammas):
        """focussing by location by applying convolutional shift
        
        Parameters:
        -----------
        gated_weightings: tf.Tensor
            shape: (batch_size, num_memory_vectors, num_read_and_write_heads)
        shift_weightings: tf.Tensor
            shape: (batch_size, 2 * size_conv_shift + 1, num_read_and_write_heads)
        read_and_write_gammas: tf.Tensor
            shape: (batch_size, num_read_and_write_heads)
        """
        
        convoluted_weights = tf.zeros_like(gated_weightings)
        
        size_conv_shift = int(shift_weightings.shape[1])
        
        for i in range(size_conv_shift):
            shift_index = size_conv_shift // 2 - i
            convoluted_weights += tf.manip.roll(gated_weightings, shift=shift_index, axis=1) * shift_weightings[:, i, :]
                
        read_and_write_gammas = tf.expand_dims(read_and_write_gammas, axis=1)
        
        pow_conv_weights = tf.pow(convoluted_weights, read_and_write_gammas)
        
        sharp_conv_weights = pow_conv_weights / tf.expand_dims(tf.reduce_sum(pow_conv_weights, 1), 1)
        
        #return sharp_conv_weights
        return sharp_conv_weights