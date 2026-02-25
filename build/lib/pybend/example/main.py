"""PyBend Example Application — demonstrates the framework with a simple product catalog."""
import logging
import os
import sys

# Add src/ to path for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pybend.core.app import create_app
from pybend.core.storage.sqlite_storage import SQLiteStorage
from pybend.core import config
from pybend.example.models import User, Bot, Product, Comment, Like

# Configure logging for development
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

# Create the application
storage = SQLiteStorage(config.SQLITE_DB_FILE)
app = create_app(
    models=[User, Product],
    join_models=[(Product, Comment), (Comment, Like), (Product, Like)],
    storage=storage,
    jwt_secret=config.JWT_SECRET,
    name="PyBend Example",
    version="0.7.0",
    description="Example product catalog with comments and likes",
)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
