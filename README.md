# Algo Rumble - Online Platform for Algorithmic Competitions

Algo Rumble is an interactive platform for algorithmic competitions, focused on 1-on-1 duels with support for other formats (2v2, etc.). The platform allows users to compete in real-time, solving algorithmic programming problems, and supports comprehensive development through problem topic management.

## Features

### Core Features
- **1-on-1 Competitions**: The primary format, with potential for team-based matches
- **Rating System**: Automatic opponent matching based on an ELO-like rating system
- **Problem Topic Management**: Users can add preferred topics (e.g., "graphs" or "dynamic programming") or ban topics they don't want to compete in
- **Real-time Solution Checking**: Automatic analysis of solutions with feedback
- **Rating Tables and Analytics**: Display of user progress, strengths, and weaknesses

### Technical Features
- **Authentication System**: Secure user registration and login with JWT tokens
- **Real-time Notifications**: WebSocket-based notifications for match updates
- **Match Queue System**: Kafka-based queue for matching players with similar ratings
- **Database Integration**: PostgreSQL for data storage with SQLAlchemy ORM
- **Redis Integration**: For token blocklisting and caching
- **Containerization**: Docker and Docker Compose for easy deployment

## Project Structure

```
algo-rumble-service/
├── .github/                # GitHub workflows and CI/CD configurations
├── migrations/             # Alembic database migrations
├── src/                    # Source code
│   ├── auth/               # Authentication module
│   │   ├── dependency.py   # Authentication dependencies
│   │   ├── model.py        # User model
│   │   ├── route.py        # Authentication endpoints
│   │   ├── schemas.py      # Authentication schemas
│   │   ├── service.py      # Authentication services
│   │   └── util.py         # Authentication utilities
│   ├── db/                 # Database module
│   │   ├── dependency.py   # Database dependencies
│   │   ├── main.py         # Database initialization
│   │   ├── model.py        # Base model
│   │   └── redis.py        # Redis client
│   ├── match/              # Match module
│   │   ├── models/         # Match models
│   │   ├── schemas/        # Match schemas
│   │   ├── consumer.py     # Kafka consumer for match queue
│   │   ├── route.py        # Match endpoints
│   │   ├── service.py      # Match services
│   │   └── websocket.py    # WebSocket for real-time notifications
│   ├── config.py           # Application configuration
│   └── main.py             # Application entry point
├── .env                    # Environment variables
├── .env.example            # Example environment variables
├── alembic.ini             # Alembic configuration
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile              # Docker configuration
├── Makefile                # Makefile for common commands
└── requirements.txt        # Python dependencies
```

## Setup and Installation

### Prerequisites
- Docker and Docker Compose
- Python 3.9+
- PostgreSQL
- Redis
- Kafka

### Local Development Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/algo-rumble-service.git
   cd algo-rumble-service
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   pip install -r requirements.txt
   ```

3. Copy the example environment file and update it with your configuration:
   ```bash
   copy .env.example .env
   ```

4. Run the database migrations:
   ```bash
   alembic upgrade head
   ```

5. Start the application:
   ```bash
   uvicorn src.main:app --reload
   ```

### Docker Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/algo-rumble-service.git
   cd algo-rumble-service
   ```

2. Copy the example environment file and update it with your configuration:
   ```bash
   copy .env.example .env
   ```

3. Build and start the Docker containers:
   ```bash
   docker-compose up -d
   ```

## Development Commands

### Code Formatting
To format your code using Black and isort, you can use the following command:
```bash
# Using make
make format

# Or using the provided scripts
format  # On Windows
```

You can also run the formatters individually:
```bash
# Using the provided scripts on Windows
black .  # Format with Black
isort .  # Sort imports with isort
```

Note: The `format`, `black`, and `isort` commands are available as wrapper scripts that ensure the tools are executed from your virtual environment.

### Testing
To run tests, you can use the following commands:
```bash
# Run all tests
make test

# Run auth tests only
make test-auth

# Run match tests only
make test-match

# Run tests with coverage
make test-cov
```

### Linting
To lint your code using ruff, you can use the following command:
```bash
# Using make
make lint

# Or using the provided scripts
ruff check .  # Check code with ruff
black .       # Format code with black
```

Note: The `ruff` and `black` commands are available as wrapper scripts that ensure the tools are executed from your virtual environment.

### Database Migrations
To run database migrations, you can use the following commands:
```bash
# Apply migrations
make migrate

# Create a new migration
make migrate-create message="Your migration message"
```

## API Documentation
Once the application is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Future Enhancements
1. **Problem Management System**: Implement the problem model and related functionality to manage algorithmic problems.
2. **Topic Management System**: Implement a system for users to manage their preferred and banned topics.
3. **Solution Submission and Evaluation**: Implement a system for users to submit solutions and have them evaluated in real-time.
4. **User Profile and Statistics**: Enhance user profiles with statistics, history, and achievements.
5. **Team-based Competitions**: Extend the match system to support team-based competitions.
6. **Tournament System**: Implement a tournament system for organized competitions.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
