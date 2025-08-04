import asyncio
from database import DatabaseManager

async def test():
    """
    Test function to verify database connection and retrieval.
    """
    print("Testing database connection...")
    
    try:
        response = await DatabaseManager.get_cv_by_id(5, 2)
        print(f"CV Data: {response['summary_json']}")
    except Exception as e:
        print(f"Error fetching CV: {str(e)}")

# Run the test using asyncio
if __name__ == "__main__":
    asyncio.run(test())
