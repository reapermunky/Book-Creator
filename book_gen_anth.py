#!/usr/bin/env python3
"""
Enhanced Book Creation UI for Anthropic's Claude

This script provides a Tkinter UI to create a book using Anthropic's Claude API.
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
import anthropic
from ebooklib import epub

# -------------------------------
# Configuration & API Keys Setup
# -------------------------------

# Retrieve your Anthropic API key from the environment
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not anthropic_api_key:
    print("Anthropic API key not set. Please set the ANTHROPIC_API_KEY environment variable.")
    sys.exit(1)

# Create an Anthropic client
client = anthropic.Anthropic(api_key=anthropic_api_key)

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

def call_anthropic_api(prompt: str, max_tokens: int = 500) -> str:
    """
    Calls Anthropic's Claude API and returns the response text.
    """
    try:
        response = client.messages.create(
            model="claude-3-sonnet-20240229",  # Using a more recent model
            max_tokens=max_tokens,
            temperature=0.7,
            system="You are an expert writer creating book content.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        result = response.content[0].text
        logging.debug("Received response from Anthropic API")
        return result
    except Exception as e:
        logging.error(f"Error calling Anthropic API: {e}")
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
    outline_response = call_anthropic_api(outline_prompt, max_tokens=500)
    
    try:
        # Try to extract JSON if it's wrapped in markdown code block
        if "```json" in outline_response:
            json_content = outline_response.split("```json")[1].split("```")[0].strip()
            chapters = json.loads(json_content)
        elif "```" in outline_response:
            json_content = outline_response.split("```")[1].split("```")[0].strip()
            chapters = json.loads(json_content)
        else:
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
        logging.error(f"Error parsing JSON outline: {e}. Raw response: {outline_response}")
        # Fallback: create simple chapter titles
        chapters = [f"Chapter {i+1}: {topic} - Part {i+1}" for i in range(num_chapters)]
        logging.info(f"Created fallback chapter titles: {chapters}")

    full_content = ""
    for idx, chapter_title in enumerate(chapters, start=1):
        logging.info(f"Generating content for Chapter {idx}: {chapter_title}")
        chapter_prompt = (
            f"Write a detailed and narrative chapter on '{topic}'. "
            f"The chapter title is '{chapter_title}'. "
            "Please provide a thorough discussion with full paragraphs, "
            "rich explanations, and smooth transitions between ideas. "
            "Avoid using bullet points or lists; focus on a flowing narrative."
        )
        # Increase the token limit for more detailed chapters
        chapter_text = call_anthropic_api(chapter_prompt, max_tokens=2000)
        # Format chapter content in HTML paragraphs
        chapter_html = f"<h2>Chapter {idx}: {chapter_title}</h2>\n<p>{chapter_text.replace(chr(10), '</p>\n<p>')}</p>"
        full_content += chapter_html + "\n"
        time.sleep(1)  # Pause slightly between API calls to avoid rate limits
    
    return full_content

def generate_book_cover(topic: str, output_filename: str = "cover.png") -> str:
    """
    Generates a book cover image using a placeholder service with a fallback option.
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

def compile_book_to_epub(title: str, author: str, content: str,
                         cover_image_path: str, output_file: str = "book.epub") -> str:
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

def create_book_process(topic: str, title: str, author: str,
                        output: str, num_chapters: int, cover_filename: str):
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
        master.title("Automated Book Creator (Anthropic)")
        master.geometry("600x500")  # Set a default window size
        self.create_widgets()
        
        # Create a logging text widget handler and add to logger
        self.log_text_handler = TextHandler(self.log_text)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        self.log_text_handler.setFormatter(formatter)
        logger.addHandler(self.log_text_handler)
        
        # Log initial message
        logging.info("Book Creator initialized. Enter your book details and click 'Create Book'")
        logging.info("Note: Make sure your ANTHROPIC_API_KEY environment variable is set")

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
        
        # Model selection dropdown
        ttk.Label(input_frame, text="Claude Model:").grid(row=6, column=0, sticky=tk.W)
        self.model_var = tk.StringVar(value="claude-3-sonnet-20240229")
        model_dropdown = ttk.Combobox(input_frame, textvariable=self.model_var, width=30)
        model_dropdown['values'] = (
            "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
            "claude-2.0",  # Including older models as options
            "claude-2.1",
            "claude-instant-1.2"
        )
        model_dropdown.grid(row=6, column=1, sticky=tk.W)
        
        # Create Book Button
        self.create_button = ttk.Button(input_frame, text="Create Book", command=self.run_book_creation)
        self.create_button.grid(row=7, column=0, columnspan=2, pady=10)
        
        # Log Text Widget with scrollbar
        log_frame = ttk.Frame(self.master)
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, wrap="word", height=15, state='disabled', 
                               yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Configure grid weights
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(1, weight=1)
        input_frame.columnconfigure(1, weight=1)

    def run_book_creation(self):
        # Disable the button to prevent multiple runs
        self.create_button.config(state='disabled')
        
        # Get input values
        topic = self.topic_entry.get().strip()
        title = self.title_entry.get().strip()
        author = self.author_entry.get().strip()
        
        # Basic validation
        if not topic:
            messagebox.showerror("Input Error", "Topic cannot be empty.")
            self.create_button.config(state='normal')
            return
            
        if not title:
            title = f"Book about {topic}"
            self.title_entry.insert(0, title)
            
        if not author:
            author = "Claude AI"
            self.author_entry.insert(0, author)
        
        try:
            num_chapters = int(self.chapters_entry.get().strip())
            if num_chapters <= 0:
                raise ValueError("Chapters must be positive")
        except ValueError:
            messagebox.showerror("Input Error", "Chapters must be a positive integer.")
            self.create_button.config(state='normal')
            return
            
        output = self.output_entry.get().strip()
        if not output.endswith('.epub'):
            output += '.epub'
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, output)
            
        cover = self.cover_entry.get().strip()
        if not cover:
            cover = "cover.png"
            self.cover_entry.insert(0, cover)
        
        # Update the model in the API call function
        global client
        selected_model = self.model_var.get()
        
        # Run the book creation process in a separate thread
        thread = threading.Thread(
            target=self.threaded_create_book,
            args=(topic, title, author, output, num_chapters, cover, selected_model)
        )
        thread.start()

    def threaded_create_book(self, topic, title, author, output, num_chapters, cover, model):
        # Override the call_anthropic_api function to use the selected model
        def model_specific_call(prompt, max_tokens=500):
            try:
                # For claude-3 models
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=0.7,
                    system="You are an expert writer creating book content.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                result = response.content[0].text
                return result
            except Exception as e:
                logging.error(f"Error calling Anthropic API with model {model}: {e}")
                # If the error is a 404, try matching to available models
                if "404" in str(e):
                    logging.info("Model not found. Attempting to find a valid model...")
                    # Try the latest models
                    try:
                        logging.info("Trying with claude-3-opus-20240229")
                        response = client.messages.create(
                            model="claude-3-opus-20240229",
                            max_tokens=max_tokens,
                            temperature=0.7,
                            system="You are an expert writer creating book content.",
                            messages=[
                                {"role": "user", "content": prompt}
                            ]
                        )
                        result = response.content[0].text
                        logging.info("Successfully used claude-3-opus-20240229")
                        return result
                    except Exception as e2:
                        logging.error(f"Error with claude-3-opus-20240229: {e2}")
                        try:
                            logging.info("Trying with claude-3-haiku-20240307")
                            response = client.messages.create(
                                model="claude-3-haiku-20240307",
                                max_tokens=max_tokens,
                                temperature=0.7,
                                system="You are an expert writer creating book content.",
                                messages=[
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            result = response.content[0].text
                            logging.info("Successfully used claude-3-haiku-20240307")
                            return result
                        except Exception as e3:
                            logging.error(f"Error with claude-3-haiku-20240307: {e3}")
                            # Final fallback
                            try:
                                logging.info("Trying with claude-instant-1.2")
                                response = client.messages.create(
                                    model="claude-instant-1.2",
                                    max_tokens=max_tokens,
                                    temperature=0.7,
                                    system="You are an expert writer creating book content.",
                                    messages=[
                                        {"role": "user", "content": prompt}
                                    ]
                                )
                                result = response.content[0].text
                                logging.info("Successfully used claude-instant-1.2")
                                return result
                            except Exception as e4:
                                logging.error(f"All model attempts failed. Last error: {e4}")
                                raise
                else:
                    raise
        
        # Replace the global function temporarily
        global call_anthropic_api
        original_call = call_anthropic_api
        call_anthropic_api = model_specific_call
        
        try:
            logging.info(f"Starting book creation with model: {model}")
            create_book_process(topic, title, author, output, num_chapters, cover)
        finally:
            # Restore the original function
            call_anthropic_api = original_call
            # Re-enable the button after process completes
            self.master.after(0, lambda: self.create_button.config(state='normal'))

def main():
    root = tk.Tk()
    app = BookCreatorUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()