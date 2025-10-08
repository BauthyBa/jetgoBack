#!/usr/bin/env python3
"""
Script to add currency column to trips table in Supabase
Run this script to execute the SQL command to add the currency field
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from api.supabase_client import get_supabase_admin
    
    def add_currency_column():
        """Add currency column to trips table"""
        try:
            admin = get_supabase_admin()
            
            # Execute the SQL to add currency column
            sql = """
            ALTER TABLE public.trips 
            ADD COLUMN IF NOT EXISTS currency text DEFAULT 'USD';
            
            COMMENT ON COLUMN public.trips.currency IS 'Currency code for budget fields (e.g., USD, EUR, ARS)';
            """
            
            result = admin.rpc('exec_sql', {'sql': sql}).execute()
            print("✅ Currency column added successfully to trips table")
            return True
            
        except Exception as e:
            print(f"❌ Error adding currency column: {e}")
            return False
    
    if __name__ == "__main__":
        print("🔄 Adding currency column to trips table...")
        success = add_currency_column()
        if success:
            print("✅ Currency functionality is now ready!")
        else:
            print("❌ Failed to add currency column. Please run the SQL manually in Supabase dashboard.")
            
except ImportError as e:
    print(f"❌ Error importing Supabase client: {e}")
    print("Please ensure the environment variables are set correctly.")
    print("You can also run the SQL manually in the Supabase dashboard:")
    print("ALTER TABLE public.trips ADD COLUMN currency text DEFAULT 'USD';")
