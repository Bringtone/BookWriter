import os
import re
import streamlit as st
from openai import OpenAI
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from dotenv import load_dotenv

load_dotenv(dotenv_path="C:/Users/user/PycharmProjects/BookWriter/secret.env")

# Provide your OpenAI API key here or via an environment variable
API_KEY = os.environ.get("OPENAI_API_KEY")
VALID_PASSWORD = os.environ.get("STREAMLIT_APP_PASSWORD")
MODEL_NAME = "gpt-4o"  # or "gpt-3.5-turbo", "gpt-4", etc.

client = OpenAI(api_key=API_KEY)


def password_protect():
    """
    Simple password gate for Streamlit.
    """
    # If not authenticated, show a password input
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        st.title("Login")
        pwd = st.text_input("Enter the password:", type="password")
        if st.button("Log in"):
            if pwd == VALID_PASSWORD:
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("Invalid password")

        # Stop execution of the app here until logged in
        st.stop()


# 2) Call the function to password-protect the app
password_protect()


def call_openai_chat_api(messages, model=MODEL_NAME, temperature=0.7):
    """
    Calls the Chat API using your approach: client.chat.completions.create(...)
    """
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )
    return completion.choices[0].message.content.strip()


# -----------------------------------------------------------------
# 2. CORE BOOK-GENERATION LOGIC
# -----------------------------------------------------------------

def choose_chapter_count(desired_pages):
    """
    Basic heuristic: 1 chapter per 5 pages, min 5, max 20.
    """
    estimated = desired_pages // 5
    if estimated < 5:
        return 5
    elif estimated > 20:
        return 20
    else:
        return estimated


def generate_outline(book_premise, desired_pages, chapter_count):
    """
    Use your approach to generate a multi-chapter outline.
    """
    system_message = {
        "role": "system",
        "content": (
            "You are an experienced author who creates professional, refined book outlines. "
            "Do not use special symbols (*, #, etc.) or bullet points. Write with a natural tone, "
            "like a real book. Number each chapter in a simple, clear manner."
        )
    }
    user_prompt = (
        f"User premise:\n{book_premise}\n\n"
        f"Please write a concise outline for a book with exactly {chapter_count} chapters, "
        f"aiming for ~{desired_pages} pages total. Number each chapter plainly (e.g., 'Chapter 1: Title'). "
        "Avoid repeating headings or using special characters. Keep it short and professional."
    )
    user_message = {"role": "user", "content": user_prompt}

    outline = call_openai_chat_api([system_message, user_message])
    return outline


def generate_chapter(chapter_title, summary_so_far, book_premise, words_for_this_chapter=300):
    """
    Generates text for a single chapter using your client.chat.completions.create approach.
    """
    system_message = {
        "role": "system",
        "content": (
            "You are an experienced author writing one chapter at a time. "
            "Write in a professional, cohesive style with multiple paragraphs, "
            "and avoid special symbols like *, #, or bullet points. "
            "Do not restate the chapter heading. Keep paragraphs substantial."
        )
    }
    user_prompt = (
        f"Book premise:\n{book_premise}\n\n"
        f"Summary of previous chapters:\n{summary_so_far}\n\n"
        f"Next chapter title: '{chapter_title}'. "
        f"Please write around {words_for_this_chapter} words. "
        "Write multiple paragraphs of continuous prose, refined and engaging. "
        "Do not repeat the chapter heading."
    )
    user_message = {"role": "user", "content": user_prompt}

    chapter_text = call_openai_chat_api([system_message, user_message])
    # Remove heading if repeated
    if chapter_text.lower().startswith(chapter_title.lower()):
        chapter_text = chapter_text[len(chapter_title):].strip(":., \n")

    return chapter_text.strip()


# -----------------------------------------------------------------
# 3. PDF GENERATION WITH REPORTLAB
# -----------------------------------------------------------------

def save_as_pdf(chapters, filename="book_output.pdf"):
    """
    Takes a list of (chapter_title, chapter_text) pairs and creates a PDF.
    Chapter titles in bigger font, chapter text in normal font.
    """
    c = canvas.Canvas(filename, pagesize=LETTER)
    width, height = LETTER

    margin_left = inch
    margin_top = height - inch

    for i, (title, text) in enumerate(chapters, start=1):
        # Title in bigger font
        c.setFont("Times-Roman", 18)
        c.drawString(margin_left, margin_top, title)

        # Move down after title
        y_pos = margin_top - 36  # ~0.5 inch lower
        c.setFont("Times-Roman", 12)
        max_chars_per_line = 90

        paragraphs = text.split("\n")
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            while len(paragraph) > max_chars_per_line:
                idx = paragraph.rfind(" ", 0, max_chars_per_line)
                if idx == -1:
                    idx = max_chars_per_line
                line = paragraph[:idx].strip()
                c.drawString(margin_left, y_pos, line)
                y_pos -= 14
                paragraph = paragraph[idx:].strip()
                if y_pos < inch:
                    c.showPage()
                    c.setFont("Times-Roman", 12)
                    y_pos = margin_top
            if paragraph:
                c.drawString(margin_left, y_pos, paragraph)
                y_pos -= 14

            # extra space after paragraph
            y_pos -= 10
            if y_pos < inch:
                c.showPage()
                c.setFont("Times-Roman", 12)
                y_pos = margin_top

        # page break after each chapter
        c.showPage()

    c.save()
    return filename


# -----------------------------------------------------------------
# 4. STREAMLIT APP
# -----------------------------------------------------------------

def main():
    st.title("Book Generator")

    # 1) Book Config
    st.header("Book Configuration")
    book_premise = st.text_area("Enter a brief explanation/premise for your book:", height=200)
    desired_pages = st.number_input("Approximate Page Count:", min_value=1, max_value=999, value=25)

    if st.button("Generate Outline"):
        total_words = desired_pages * 300
        chapter_count = choose_chapter_count(desired_pages)
        words_per_chapter = max(200, total_words // chapter_count)

        # Generate outline
        outline = generate_outline(book_premise, desired_pages, chapter_count)

        st.session_state["outline_raw"] = outline
        st.session_state["chapter_count"] = chapter_count
        st.session_state["words_per_chapter"] = words_per_chapter
        st.session_state["summary_so_far"] = ""
        st.session_state["chapters_data"] = []
        st.session_state["edited_outline"] = outline

    if "outline_raw" in st.session_state:
        st.header("Proposed Outline")

        # Let user edit the outline
        st.session_state["edited_outline"] = st.text_area(
            "Edit your outline (Keep 'Chapter X: Title' lines intact):",
            value=st.session_state["edited_outline"],
            height=300
        )

        if st.button("Confirm Outline"):
            # Parse
            lines = st.session_state["edited_outline"].split("\n")
            chapter_lines = []
            for line in lines:
                strip_line = line.strip()
                if re.match(r"(?i)^chapter\s+\d+:", strip_line):
                    chapter_lines.append(strip_line)

            # Truncate or fill placeholders to match chapter_count
            chapter_count = st.session_state["chapter_count"]
            chapter_lines = chapter_lines[:chapter_count]
            while len(chapter_lines) < chapter_count:
                idx = len(chapter_lines) + 1
                chapter_lines.append(f"Chapter {idx}: Untitled")

            st.session_state["chapter_lines"] = chapter_lines
            st.success("Outline confirmed! Generate chapters next.")

    if "chapter_lines" in st.session_state:
        st.header("Generate or Edit Chapters")
        if st.button("Generate All Chapters"):
            st.session_state["chapters_data"] = []
            summary_so_far = ""
            words_ch = st.session_state["words_per_chapter"]
            for i, ch_title in enumerate(st.session_state["chapter_lines"], start=1):
                st.write(f"Generating Chapter {i}: {ch_title}")
                chapter_text = generate_chapter(
                    ch_title,
                    summary_so_far,
                    book_premise,
                    words_ch
                )
                st.session_state["chapters_data"].append({
                    "title": ch_title,
                    "text": chapter_text
                })
                summary_so_far += f"[{ch_title}] {chapter_text[:500]}...\n"

            st.success("Chapters generated! You can now edit them below.")

        # Edit chapters
        if st.session_state.get("chapters_data"):
            for i, ch in enumerate(st.session_state["chapters_data"]):
                st.subheader(ch["title"])
                new_text = st.text_area(
                    f"Edit {ch['title']}",
                    value=ch["text"],
                    height=200
                )
                st.session_state["chapters_data"][i]["text"] = new_text

            # Compile PDF
            if st.button("Compile PDF"):
                final_chapters = []
                for ch in st.session_state["chapters_data"]:
                    final_chapters.append((ch["title"], ch["text"]))

                pdf_file = "book_output.pdf"
                save_as_pdf(final_chapters, pdf_file)
                st.success(f"PDF generated: {pdf_file}")

                # Download button
                with open(pdf_file, "rb") as f:
                    pdf_data = f.read()
                st.download_button(
                    label="Download PDF",
                    data=pdf_data,
                    file_name="GeneratedBook.pdf",
                    mime="application/pdf"
                )


if __name__ == "__main__":
    main()
