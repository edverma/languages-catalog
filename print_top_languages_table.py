import sqlite3
import json

def print_top_languages_table():
    # Connect to the database
    conn = sqlite3.connect('languages.db')
    c = conn.cursor()
    
    # Open file for writing
    with open('top_languages.md', 'w', encoding='utf-8') as f:
        # Query for top 200 languages by native speakers, excluding null values
        query = '''
        SELECT name, native_speakers, language_family, standard_forms, dialects, glottolog, url
        FROM languages 
        WHERE native_speakers IS NOT NULL
        and language_family IS NOT NULL
        ORDER BY native_speakers DESC
        LIMIT 200
        '''
        
        c.execute(query)
        results = c.fetchall()
        
        # Get column names from cursor description
        columns = [description[0] for description in c.description]
        
        # Write markdown table header
        header = " | ".join(["Rank"] + [col.replace('_', ' ').title() for col in columns])
        f.write(f"| {header} |\n")
        f.write("|" + "|".join(["------"] * (len(columns) + 1)) + "|\n")
        
        # Write each row
        for rank, row in enumerate(results, 1):
            formatted_row = []
            for i, value in enumerate(row):
                if columns[i] == 'native_speakers' and value is not None:
                    formatted_value = f"{int(value):,}"
                elif columns[i] == 'language_family' and value:
                    try:
                        family_list = json.loads(value)
                        formatted_value = family_list[0] if family_list else "Unknown"
                    except json.JSONDecodeError:
                        formatted_value = value if value else "Unknown"
                elif columns[i] == 'dialects' and value:
                    try:
                        dialect_list = json.loads(value)
                        formatted_value = '\n'.join(dialect_list) if dialect_list else ""
                    except json.JSONDecodeError:
                        formatted_value = value if value else ""
                else:
                    formatted_value = str(value) if value is not None else ""
                formatted_row.append(formatted_value)
                
            f.write(f"| {rank} | {' | '.join(formatted_row)} |\n")
    
    conn.close()

if __name__ == "__main__":
    print_top_languages_table()
