"""CLI test for RAG pipeline."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.pipeline import generate_answer


def main():
    print("RAG Pipeline Test (type 'quit' to exit)")
    print("-" * 40)
    while True:
        question = input("\nQuestion: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue
        print("Thinking...")
        answer = generate_answer(question)
        print(f"\nAnswer: {answer}")


if __name__ == "__main__":
    main()
