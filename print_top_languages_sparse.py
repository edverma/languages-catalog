import sqlite3

def print_top_languages_table():
    # Connect to the database
    conn = sqlite3.connect('languages.db')
    c = conn.cursor()
    
    # Open file for writing
    with open('top_languages_sparse.md', 'w', encoding='utf-8') as f:
        # Query for top 100 languages by native speakers, excluding null values
        query = '''
        SELECT name, native_speakers
        FROM languages 
        WHERE native_speakers IS NOT NULL
        AND language_family IS NOT NULL
        ORDER BY native_speakers DESC
        LIMIT 100
        '''
        
        c.execute(query)
        results = c.fetchall()
        
        # Write markdown table header
        f.write("| Rank | Name | Native Speakers |\n")
        f.write("|------|------|----------------|\n")
        
        # Write each row
        for rank, row in enumerate(results, 1):
            name, speakers = row
            formatted_speakers = f"{int(speakers):,}" if speakers is not None else ""
            f.write(f"| {rank} | {name} | {formatted_speakers} |\n")
    
    conn.close()

if __name__ == "__main__":
    print_top_languages_table()
