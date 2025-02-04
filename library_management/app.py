from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from werkzeug.utils import secure_filename
from threading import Timer
import webbrowser

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Function to connect to the database
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Home page
@app.route('/')
def index():
    conn = get_db_connection()
    # 総蔵書数
    total_books = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
    # 貸出中の本
    checked_out_books = conn.execute('SELECT COUNT(*) FROM books WHERE is_checked_out = 1').fetchone()[0]
    # 利用可能な本
    available_books = conn.execute('SELECT COUNT(*) FROM books WHERE is_checked_out = 0').fetchone()[0]
    conn.close()

    return render_template('index.html', 
                           total_books=total_books, 
                           checked_out_books=checked_out_books, 
                           available_books=available_books)

# Display list of books
@app.route('/books', methods=('GET', 'POST'))
def books():
    conn = get_db_connection()
    if request.method == 'POST':
        if 'show_all' in request.form:  # "Show All" ボタンが押された場合
            books = conn.execute('SELECT * FROM books').fetchall()
        else:  # 通常の検索処理
            search_query = request.form.get('search', '')  # 検索クエリを取得
            books = conn.execute(
                'SELECT * FROM books WHERE title LIKE ? OR isbn LIKE ?', 
                ('%' + search_query + '%', '%' + search_query + '%')
            ).fetchall()
    else:
        books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return render_template('books.html', books=books)

# Add a new book
@app.route('/add_book', methods=('GET', 'POST'))
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        isbn = request.form['isbn']

        # Handle file upload
        file = request.files['cover_image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
        else:
            filename = None

        conn = get_db_connection()
        conn.execute('INSERT INTO books (title, author, isbn, cover_image, is_checked_out, borrower_name) VALUES (?, ?, ?, ?, ?, ?)',
                     (title, author, isbn, filename, 0, None))
        conn.commit()
        conn.close()
        return redirect(url_for('books'))
    return render_template('add_book.html')

# Toggle book checkout status
@app.route('/toggle_checkout/<int:book_id>', methods=['POST'])
def toggle_checkout(book_id):
    borrower_name = request.form.get('borrower_name', None)  # Borrower's name from the form
    conn = get_db_connection()
    current_status = conn.execute('SELECT is_checked_out FROM books WHERE id = ?', (book_id,)).fetchone()['is_checked_out']

    if current_status:  # Returning the book
        conn.execute('UPDATE books SET is_checked_out = 0, borrower_name = NULL WHERE id = ?', (book_id,))
    else:  # Checking out the book
        if not borrower_name:
            flash('Borrower name is required to check out the book.')
            return redirect(url_for('books'))
        conn.execute('UPDATE books SET is_checked_out = 1, borrower_name = ? WHERE id = ?', (borrower_name, book_id))

    conn.commit()
    conn.close()
    return redirect(url_for('books'))

# Delete a book
@app.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    conn = get_db_connection()
    
    # Get the cover image filename
    book = conn.execute('SELECT cover_image FROM books WHERE id = ?', (book_id,)).fetchone()
    if book and book['cover_image']:
        cover_image_path = os.path.join(app.config['UPLOAD_FOLDER'], book['cover_image'])
        try:
            if os.path.exists(cover_image_path):
                os.remove(cover_image_path)  # Remove the image file
        except Exception as e:
            flash(f"Error deleting the image: {e}")

    # Delete the book from the database
    conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))

# Auto-open browser function
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    # Create the database and table if they do not exist
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT NOT NULL,
            cover_image TEXT,
            is_checked_out INTEGER DEFAULT 0,
            borrower_name TEXT
        )
    ''')
    conn.commit()
    conn.close()

    # Prevent double browser opening in debug mode
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        Timer(1, open_browser).start()  # 1秒後にブラウザを開く

    # Start the Flask application
    app.run(host="0.0.0.0", port=5000, debug=True)
