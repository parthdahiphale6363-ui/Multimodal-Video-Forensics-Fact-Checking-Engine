import argparse
import logging
import sys
import os

from dotenv import load_dotenv

# Load env variables (GROQ_API_KEY)
load_dotenv()

# Add root folder to sys.path if run directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from transcription.groq_translator import GroqTranslator, SilentAudioError, GroqTranslationError

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Standalone test for Groq audio translation.")
    parser.add_argument("--audio", required=True, help="Path to the audio file to translate.")
    parser.add_argument("--language", help="Optional source language hint (ISO 639-1, e.g. es, hi, ar)")
    args = parser.parse_args()

    if not os.path.exists(args.audio):
        logger.error(f"File not found: {args.audio}")
        sys.exit(1)

    try:
        translator = GroqTranslator()
        logger.info(f"Translating {args.audio}...")
        
        result = translator.translate_audio(args.audio, language_hint=args.language)
        
        print("\n" + "="*50)
        print(f"Detected Source Language: {result.detected_source_language.upper()}")
        print(f"Total Segments: {len(result.segments)}")
        print(f"Chunks Processed: {result.chunk_count}")
        print(f"Duration Processed: {result.audio_duration_seconds:.2f} seconds")
        print("="*50)
        print("\n[TRANSLATED ENGLISH TEXT]:")
        print(result.english_text)
        print("\n" + "="*50)
        
        if result.original_language_text:
            print("\n[ORIGINAL SCRIPT (Safety Net)]:")
            print(result.original_language_text)
            print("\n" + "="*50)

    except SilentAudioError as e:
        logger.warning(f"Audio flagged as silent: {e}")
        sys.exit(2)
    except GroqTranslationError as e:
        logger.error(f"Translation failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
