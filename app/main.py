import os
import sqlite3
import subprocess
import datetime

class RepoSearchApp:
    def __init__(self, repos_dir='repos', db_path='repo_search.db'):
        """
        Initialize the application with repositories directory and database path
        
        :param repos_dir: Directory to clone repositories into
        :param db_path: Path to SQLite database
        """
        self.repos_dir = repos_dir
        self.db_path = db_path
        
        # Create repos directory if it doesn't exist
        os.makedirs(repos_dir, exist_ok=True)
        
        # Initialize database connection
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Create tables with FTS5 support
        self.cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS file_contents USING fts5(
                repo_name, 
                filepath, 
                filename, 
                content, 
                last_modified
            )
        ''')
        self.conn.commit()

    def clone_repo(self, repo_url):
        """
        Clone a repository 
        
        :param repo_url: URL of the git repository
        :return: Name of the cloned repository directory
        """
        # Extract repo name from URL
        repo_name = os.path.splitext(os.path.basename(repo_url))[0]
        repo_path = os.path.join(self.repos_dir, repo_name)
        
        # Clone repository
        try:
            # Remove existing repo if it exists
            if os.path.exists(repo_path):
                subprocess.run(['rm', '-rf', repo_path], check=True)
            
            # Clone the repository
            subprocess.run(['git', 'clone', repo_url, repo_path], check=True)
            return repo_name
        except subprocess.CalledProcessError as e:
            print(f"Error cloning {repo_url}: {e}")
            return None

    def index_repository(self, repo_name):
        """
        Index all files in a cloned repository
        
        :param repo_name: Name of the repository to index
        """
        repo_path = os.path.join(self.repos_dir, repo_name)
        
        # Walk through all files in the repository
        for root, _, files in os.walk(repo_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                
                # Skip binary and very large files
                try:
                    # Only process text files under a certain size
                    if os.path.getsize(filepath) > 1_000_000:  # Skip files larger than 1MB
                        continue
                    
                    # Try to read file content
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # Skip files that can't be read as UTF-8
                        continue
                    
                    # Get file stats
                    file_stats = os.stat(filepath)
                    last_modified = datetime.datetime.fromtimestamp(file_stats.st_mtime).isoformat()
                    
                    # Compute relative path
                    relative_path = os.path.relpath(filepath, repo_path)
                    
                    # Insert file content into FTS table
                    self.cursor.execute('''
                        INSERT INTO file_contents 
                        (repo_name, filepath, filename, content, last_modified) 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        repo_name, 
                        relative_path, 
                        filename, 
                        content, 
                        last_modified
                    ))
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
        
        # Commit changes
        self.conn.commit()

    def index_repositories(self, repo_urls):
        """
        Clone and index multiple repositories
        
        :param repo_urls: List of repository URLs to clone and index
        """
        # Clear existing index
        self.cursor.execute('DELETE FROM file_contents')
        self.conn.commit()
        
        for repo_url in repo_urls:
            repo_name = self.clone_repo(repo_url)
            if repo_name:
                self.index_repository(repo_name)

    def search_files(self, query, limit=50):
        """
        Search files using SQLite FTS
        
        :param query: Search query string
        :param limit: Maximum number of results to return
        :return: List of matching files
        """
        self.cursor.execute('''
            SELECT repo_name, filepath, filename, 
                   snippet(file_contents, 0, '...', '...', '...', 50) as preview
            FROM file_contents
            WHERE file_contents MATCH ?
            LIMIT ?
        ''', (query, limit))
        return self.cursor.fetchall()

    def __del__(self):
        """
        Close database connection
        """
        if hasattr(self, 'conn'):
            self.conn.close()

# Flask web interface
from flask import Flask, render_template, request

app = Flask(__name__)
repo_search = RepoSearchApp()

@app.route('/', methods=['GET'])
def index():
    """
    Render the main search page
    """
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """
    Handle search requests and display results
    """
    # Get search query from form
    query = request.form.get('query', '')
    
    # Perform search
    results = repo_search.search_files(query)
    
    # Render results template
    return render_template('results.html', 
                           query=query, 
                           results=results)

def setup_initial_repos():
    """
    Initial setup to clone and index repositories
    """
    repos_to_index = [
        'https://github.com/runarhageland/strompris.git',
        'https://github.com/runarhageland/k8slab.git'
    ]
    
    # Clone and index repositories
    repo_search.index_repositories(repos_to_index)

if __name__ == '__main__':
    # Setup initial repositories before starting the app
    setup_initial_repos()
    print(os.environ['FLASK_RUN_HOST'])
    
    # Run the Flask app
    app.run(host=(os.environ['FLASK_RUN_HOST']), port=(os.environ['FLASK_RUN_PORT']), debug=(os.environ['DEBUG']))