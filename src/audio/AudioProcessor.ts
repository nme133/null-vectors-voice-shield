import { AudioProcessorConfig, AudioProcessorState, TARGET_SAMPLE_RATE } from './audioTypes';

/**
 * AudioProcessor: Resamples microphone audio from browser sample rate to 16 kHz
 * and emits fixed-size audio chunks.
 *
 * Pipeline:
 * Float32 PCM (any sample rate)
 * → linear interpolation resampling to 16 kHz
 * → accumulate into fixed-size chunks (16000 samples = 1 second)
 * → onChunk callback for each complete chunk
 *
 * This layer sits between LiveAudioInput and future WebSocket/backend integration.
 */
export class AudioProcessor {
  private config: AudioProcessorConfig;
  private state: AudioProcessorState;
  private resamplingRatio: number;

  constructor(config: AudioProcessorConfig) {
    const targetRate = config.targetSampleRate ?? TARGET_SAMPLE_RATE;
    const chunkSize = config.chunkSize ?? TARGET_SAMPLE_RATE; // Default 1 second at 16 kHz

    if (config.inputSampleRate <= 0) {
      throw new Error('inputSampleRate must be positive');
    }
    if (targetRate <= 0) {
      throw new Error('targetSampleRate must be positive');
    }
    if (chunkSize <= 0) {
      throw new Error('chunkSize must be positive');
    }

    this.config = {
      ...config,
      targetSampleRate: targetRate,
      chunkSize: chunkSize
    };

    // Ratio for resampling: output_sample_rate / input_sample_rate
    // If inputRate=48000 and targetRate=16000, ratio=1/3
    this.resamplingRatio = targetRate / config.inputSampleRate;

    // Initialize resampled buffer
    // Size it to hold more than one chunk to handle buffering
    const bufferSize = chunkSize * 2;
    this.state = {
      resampledBuffer: new Float32Array(bufferSize),
      bufferPosition: 0,
      samplesProcessed: 0
    };
  }

  /**
   * Process incoming microphone audio samples.
   * May trigger onChunk callback zero or more times depending on buffering.
   *
   * @param audioData Float32Array of PCM samples from microphone
   */
  public processAudioData(audioData: Float32Array): void {
    console.log("🎤 PROCESSING AUDIO:", audioData.length);
    if (!audioData || audioData.length === 0) {
      return;
    }

    // Resample the incoming audio data
    const resampledData = this.resample(audioData);

    // Add resampled samples to buffer and emit chunks as needed
    this.accumulateAndEmitChunks(resampledData);
  }

  /**
   * Resample incoming audio from input sample rate to target sample rate.
   * Uses linear interpolation for high-quality real-time resampling.
   *
   * @param audioData Float32Array at input sample rate
   * @returns Float32Array at target sample rate
   */
  private resample(audioData: Float32Array): Float32Array {
    // Calculate number of output samples from this input
    const outputLength = Math.ceil(audioData.length * this.resamplingRatio);
    const output = new Float32Array(outputLength);

    // Linear interpolation resampling
    for (let outputIndex = 0; outputIndex < outputLength; outputIndex++) {
      // Map output index to input position
      const inputPosition = outputIndex / this.resamplingRatio;

      const lowerIndex = Math.floor(inputPosition);
      const upperIndex = lowerIndex + 1;
      const fraction = inputPosition - lowerIndex;

      let sample: number;

      if (upperIndex < audioData.length) {
        // Interpolate between two samples
        const lower = audioData[lowerIndex];
        const upper = audioData[upperIndex];
        sample = lower * (1 - fraction) + upper * fraction;
      } else if (lowerIndex < audioData.length) {
        // Only lower sample available
        sample = audioData[lowerIndex];
      } else {
        // Beyond buffer bounds (shouldn't happen in normal operation)
        sample = 0;
      }

      output[outputIndex] = sample;
    }

    return output;
  }

  /**
   * Accumulate resampled samples and emit chunks when buffer is full.
   * Any overflow is retained for the next call.
   */
  private accumulateAndEmitChunks(resampledData: Float32Array): void {
    const chunkSize = this.config.chunkSize!;
    let resampledIndex = 0;

    while (resampledIndex < resampledData.length) {
      const remainingInChunk = chunkSize - this.state.bufferPosition;
      const remainingInData = resampledData.length - resampledIndex;
      const toCopy = Math.min(remainingInChunk, remainingInData);

      // Copy data into buffer
      this.state.resampledBuffer.set(
        resampledData.slice(resampledIndex, resampledIndex + toCopy),
        this.state.bufferPosition
      );

      this.state.bufferPosition += toCopy;
      resampledIndex += toCopy;

      // If buffer is full, emit a chunk
      if (this.state.bufferPosition >= chunkSize) {
        console.log("🚀 CHUNK READY:", this.state.bufferPosition);
        this.emitChunk();
      }
    }
  }

  /**
   * Emit a complete chunk and reset buffer position.
   */
  private emitChunk(): void {
    const chunkSize = this.config.chunkSize!;
    const chunk = this.state.resampledBuffer.slice(0, chunkSize);

    if (this.config.onChunk) {
        console.log("📤 CALLING onChunk:", chunk.length);
        this.config.onChunk(chunk);
    } else {
      console.log("❌ NO onChunk CALLBACK");
    }

    // Shift remaining samples to start of buffer
    if (this.state.bufferPosition > chunkSize) {
      const remaining = this.state.bufferPosition - chunkSize;
      this.state.resampledBuffer.set(
        this.state.resampledBuffer.slice(chunkSize, chunkSize + remaining),
        0
      );
      this.state.bufferPosition = remaining;
    } else {
      this.state.bufferPosition = 0;
    }
  }

  /**
   * Flush any remaining buffered samples as a partial chunk.
   * Call this when monitoring stops.
   */
  public flush(): void {
    if (this.state.bufferPosition > 0) {
      const remainingChunk = this.state.resampledBuffer.slice(0, this.state.bufferPosition);

      if (this.config.onChunk) {
        this.config.onChunk(remainingChunk);
      }

      this.state.bufferPosition = 0;
    }
  }

  /**
   * Reset the processor state. Call when monitoring stops.
   */
  public reset(): void {
    this.flush();
    const chunkSize = this.config.chunkSize!;
    const bufferSize = chunkSize * 2;
    this.state.resampledBuffer = new Float32Array(bufferSize);
    this.state.bufferPosition = 0;
  }

  /**
   * Get current processor state (for debugging/monitoring)
   */
  public getState(): Readonly<AudioProcessorState> {
    return { ...this.state };
  }

  /**
   * Get configuration
   */
  public getConfig(): Readonly<AudioProcessorConfig> {
    return { ...this.config };
  }
}
