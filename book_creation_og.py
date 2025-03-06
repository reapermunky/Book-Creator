#!/usr/bin/env python3
"""
Enhanced Book Creation UI

This script provides a Tkinter UI to create a book using the OpenAI API.
It generates a structured outline, produces detailed narrative chapters,
fetches a cover image (with fallback), and compiles the content into an EPUB file.
"""

import os
import sys
import time
import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List

import requests
import openai
from ebooklib import epub

# -------------------------------
# Configuration & API Keys Setup
# -------------------------------

# Set your OpenAI API key (via environment variable or assign directly)
openai.api_key = os.environ.get("OPENAI_API_KEY")  # e.g., "sk-...your_key_here..."
if not openai.api_key:
    print("OpenAI API key not set. Please set the OPENAI_API_KEY environment variable.")
    sys.exit(1)

# -------------------------------
# Logging Setup: Log to both console and Tkinter Text widget (configured later)
# -------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class TextHandler(logging.Handler):
    """Custom logging handler that writes to a Tkinter Text widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + "\n")
            self.text_widget.configure(state='disabled')
            self.text_widget.see(tk.END)
        self.text_widget.after(0, append)

# -------------------------------
# Helper Functions
# -------------------------------

def call_openai_api(prompt: str, max_tokens: int = 500) -> str:
    """
    Calls the OpenAI ChatCompletion API and returns the response text.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            n=1,
            temperature=0.7,
        )
        result = response.choices[0].message['content'].strip()
        logging.debug("Received response from OpenAI API")
        return result
    except Exception as e:
        logging.error(f"Error calling OpenAI API: {e}")
        raise

# -------------------------------
# Book Generation Functions
# -------------------------------

def generate_book_content(topic: str, num_chapters: int = 5) -> str:
    """
    Generates book content by creating an outline (in JSON) and then generating each chapter.
    Returns the full book content as a single string.
    """
    logging.info("Generating book outline as JSON...")
    outline_prompt = (
        f"Generate a JSON array with exactly {num_chapters} strings. "
        f"Each string should be a concise chapter title for a book on the topic: '{topic}'. "
        "Do not include any extra text, numbering, or sub-chapter points. Return only the JSON array."
    )
    outline_response = call_openai_api(outline_prompt, max_tokens=500)
    
    try:
        chapters = json.loads(outline_response)
        if not isinstance(chapters, list):
            raise ValueError("The output is not a JSON array.")
        if len(chapters) != num_chapters:
            logging.warning(f"Expected {num_chapters} chapters, but got {len(chapters)}. Adjusting the list accordingly.")
            if len(chapters) > num_chapters:
                chapters = chapters[:num_chapters]
            else:
                while len(chapters) < num_chapters:
                    chapters.append(f"Chapter {len(chapters)+1}")
    except Exception as e:
        logging.error(f"Error parsing JSON outline: {e}")
        raise

    full_content = ""
    for idx, chapter_title in enumerate(chapters, start=1):
        logging.info(f"Generating content for Chapter {idx}: {chapter_title}")
        chapter_prompt = (
            f"Write a detailed and narrative chapter on '{topic}'. The chapter title is '{chapter_title}'. "
            "Please provide a thorough discussion with full paragraphs, rich explanations, and smooth transitions between ideas. "
            "Avoid using bullet points, lists, or fragmented points; focus on creating a flowing narrative that fully explores the topic."
        )
        # Increase the token limit for more detailed chapters (adjust as needed)
        chapter_text = call_openai_api(chapter_prompt, max_tokens=2000)
        # Format chapter content in HTML paragraphs
        chapter_html = f"<h2>Chapter {idx}: {chapter_title}</h2>\n<p>{chapter_text.replace(chr(10), '</p>\n<p>')}</p>"
        full_content += chapter_html + "\n"
        time.sleep(1)  # Pause slightly between API calls to avoid rate limits
    
    return full_content

def generate_book_cover(topic: str, output_filename: str = "cover.png") -> str:
    """
    Generates a book cover image using a primary placeholder service with a fallback option.
    """
    logging.info("Generating book cover image...")
    # Primary service URL
    base_url = "https://via.placeholder.com/600x800.png?text="
    text = topic.replace(" ", "+")
    image_url = base_url + text
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to generate cover image with primary service: {e}")
        # Fallback service URL
        fallback_base_url = "https://dummyimage.com/600x800/cccccc/000000&text="
        image_url = fallback_base_url + text
        logging.info("Attempting fallback cover image service...")
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logging.error(f"Failed to generate cover image with fallback service: {e}")
            raise
    try:
        with open(output_filename, "wb") as f:
            f.write(response.content)
        logging.info(f"Cover image saved as {output_filename}")
    except Exception as e:
        logging.error(f"Failed to save cover image: {e}")
        raise
    return output_filename

def compile_book_to_epub(title: str, author: str, content: str, cover_image_path: str, output_file: str = "book.epub") -> str:
    """
    Compiles the book's content and cover image into an EPUB file.
    """
    logging.info("Compiling content into EPUB format...")
    try:
        book = epub.EpubBook()
        book.set_identifier("id123456")
        book.set_title(title)
        book.set_language('en')
        book.add_author(author)
        
        chapter = epub.EpubHtml(title="Content", file_name="chap_01.xhtml", lang='en')
        chapter.content = f"<h1>{title}</h1>\n{content}"
        book.add_item(chapter)
        
        with open(cover_image_path, 'rb') as img_file:
            cover_image_data = img_file.read()
        book.set_cover(os.path.basename(cover_image_path), cover_image_data)
        
        book.toc = (epub.Link('chap_01.xhtml', 'Content', 'content'),)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['cover', 'nav', chapter]
        
        epub.write_epub(output_file, book)
        logging.info(f"EPUB file created: {output_file}")
        return output_file
    except Exception as e:
        logging.error(f"Failed to compile EPUB: {e}")
        raise

# -------------------------------
# Book Creation Process
# -------------------------------

def create_book_process(topic: str, title: str, author: str, output: str, num_chapters: int, cover_filename: str):
    """
    Main process for creating the book. Called in a separate thread.
    """
    try:
        content = generate_book_content(topic, num_chapters=num_chapters)
        cover_image_path = generate_book_cover(topic, output_filename=cover_filename)
        epub_file = compile_book_to_epub(title, author, content, cover_image_path, output_file=output)
        logging.info("Book creation process completed successfully!")
        logging.info(f"Your EPUB file is ready: {epub_file}")
    except Exception as e:
        logging.error(f"Book creation failed: {e}")

# -------------------------------
# Tkinter UI
# -------------------------------

class BookCreatorUI:
    def __init__(self, master):
        self.master = master
        master.title("Automated Book Creator")
        self.create_widgets()
        
        # Create a logging text widget handler and add to logger
        self.log_text_handler = TextHandler(self.log_text)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        self.log_text_handler.setFormatter(formatter)
        logger.addHandler(self.log_text_handler)

    def create_widgets(self):
        # Input Frame
        input_frame = ttk.Frame(self.master, padding="10")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Topic
        ttk.Label(input_frame, text="Topic:").grid(row=0, column=0, sticky=tk.W)
        self.topic_entry = ttk.Entry(input_frame, width=50)
        self.topic_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # Title
        ttk.Label(input_frame, text="Title:").grid(row=1, column=0, sticky=tk.W)
        self.title_entry = ttk.Entry(input_frame, width=50)
        self.title_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))
        
        # Author
        ttk.Label(input_frame, text="Author:").grid(row=2, column=0, sticky=tk.W)
        self.author_entry = ttk.Entry(input_frame, width=50)
        self.author_entry.grid(row=2, column=1, sticky=(tk.W, tk.E))
        
        # Chapters
        ttk.Label(input_frame, text="Chapters:").grid(row=3, column=0, sticky=tk.W)
        self.chapters_entry = ttk.Entry(input_frame, width=10)
        self.chapters_entry.insert(0, "5")
        self.chapters_entry.grid(row=3, column=1, sticky=tk.W)
        
        # Output EPUB filename
        ttk.Label(input_frame, text="Output EPUB:").grid(row=4, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(input_frame, width=50)
        self.output_entry.insert(0, "book.epub")
        self.output_entry.grid(row=4, column=1, sticky=(tk.W, tk.E))
        
        # Cover image filename
        ttk.Label(input_frame, text="Cover Image:").grid(row=5, column=0, sticky=tk.W)
        self.cover_entry = ttk.Entry(input_frame, width=50)
        self.cover_entry.insert(0, "cover.png")
        self.cover_entry.grid(row=5, column=1, sticky=(tk.W, tk.E))
        
        # Create Book Button
        self.create_button = ttk.Button(input_frame, text="Create Book", command=self.run_book_creation)
        self.create_button.grid(row=6, column=0, columnspan=2, pady=10)
        
        # Log Text Widget
        self.log_text = tk.Text(self.master, wrap="word", height=15, state='disabled')
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Configure grid weights
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(1, weight=1)

    def run_book_creation(self):
        # Disable the button to prevent multiple runs
        self.create_button.config(state='disabled')
        
        # Get input values
        topic = self.topic_entry.get().strip()
        title = self.title_entry.get().strip()
        author = self.author_entry.get().strip()
        try:
            num_chapters = int(self.chapters_entry.get().strip())
        except ValueError:
            messagebox.showerror("Input Error", "Chapters must be an integer.")
            self.create_button.config(state='normal')
            return
        output = self.output_entry.get().strip()
        cover = self.cover_entry.get().strip()
        
        # Run the book creation process in a separate thread
        thread = threading.Thread(target=self.threaded_create_book, args=(topic, title, author, output, num_chapters, cover))
        thread.start()

    def threaded_create_book(self, topic, title, author, output, num_chapters, cover):
        create_book_process(topic, title, author, output, num_chapters, cover)
        # Re-enable the button after process completes
        self.master.after(0, lambda: self.create_button.config(state='normal'))

def main():
    root = tk.Tk()
    app = BookCreatorUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()