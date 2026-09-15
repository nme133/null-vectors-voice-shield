/**
 * Target streaming format:
 * - Sample rate: 16000 Hz
 * - Channels: 1 (mono)
 * - Format: Float32 PCM internally
 * - Later conversion to Int16 PCM bytes for backend as needed
 */

export const TARGET_SAMPLE_RATE = 16000;

export interface AudioProcessorConfig {
  /**
   * Browser's AudioContext sample rate (e.g., 48000 Hz, 44100 Hz)
   */
  inputSampleRate: number;

  /**
   * Target sample rate for resampled output (default: 16000 Hz)
   */
  targetSampleRate?: number;

  /**
   * Size of each audio chunk in samples.
   * Default: 16000 (1 second at 16 kHz)
   */
  chunkSize?: number;

  /**
   * Callback fired when a complete audio chunk is ready
   */
  onChunk?: (chunk: Float32Array) => void;
}

export interface AudioProcessorState {
  /**
   * Buffer for resampled audio samples waiting to be chunked
   */
  resampledBuffer: Float32Array;

  /**
   * Current write position in the resampled buffer
   */
  bufferPosition: number;

  /**
   * Number of input samples processed so far (for tracking)
   */
  samplesProcessed: number;
}
