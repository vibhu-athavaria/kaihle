# Kaihle Platform Backend

A comprehensive FastAPI backend for a Kaihle platform with user authentication, student progress tracking, lesson management, AI tutor integration, and community features.

## Features

- **Authentication & Authorization**: JWT-based auth with role-based access control (parent, student, admin)
- **User Management**: Complete CRUD operations for user profiles and student management
- **Progress Tracking**: Weekly progress monitoring, badges, and achievements system
- **Lesson Management**: Full lesson CRUD with study plans and completion tracking
- **AI Tutor Integration**: Personalized recommendations, answer evaluation, and chat functionality
- **Community Features**: Discussion posts, comments, and user interactions
- **Notifications**: Real-time notification system for user engagement

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT tokens with bcrypt password hashing
- **Migration**: Alembic for database migrations
- **Testing**: pytest (ready for implementation)

## Project Structure

\`\`\`
app/
├── api/v1/              # API endpoints
├── core/                # Core configuration and dependencies
├── crud/                # Database operations
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── services/            # Business logic services
└── main.py              # FastAPI application

scripts/                 # Database and utility scripts
alembic/                 # Database migration files
\`\`\`

## Setup Instructions

1. **Create Virtual Environment**
   \`\`\`bash
   python3 -m venv venv
   \`\`\`

2. **Activate Virtual Environment**
   \`\`\`bash
   source venv/bin/activate
   \`\`\`

3. **Install Dependencies**
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

4. **Configure Database**
   - Update `DATABASE_URL` in `app/core/config.py`
   - Or set environment variables in `.env` file

5. **Run Database Migrations**
   \`\`\`bash
   python scripts/create_initial_migration.py
   python scripts/run_migrations.py
   \`\`\`

6. **Seed Initial Data**
   \`\`\`bash
   python scripts/seed_initial_data.py
   \`\`\`

7. **Start the Server**
   \`\`\`bash
   uvicorn app.main:app --reload
   \`\`\`

## API Documentation

Once running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Key Endpoints

### Authentication
- `POST /api/v1/auth/signup` - Create new user account
- `POST /api/v1/auth/login` - Authenticate and get JWT token
- `POST /api/v1/auth/logout` - Logout user

### User Management
- `GET /api/v1/users/me` - Get current user profile
- `PUT /api/v1/users/me` - Update user profile
- `GET /api/v1/users/me/students` - Get user's students (parents)

### Progress Tracking
- `GET /api/v1/progress/{student_id}` - Get student progress summary
- `POST /api/v1/progress/{student_id}` - Update student progress
- `GET /api/v1/progress/badges` - Get available badges

### Lessons & Study Plans
- `GET /api/v1/lessons` - Get all lessons
- `POST /api/v1/lessons` - Create new lesson (admin)
- `GET /api/v1/study-plans/student/{student_id}` - Get student's study plans
- `POST /api/v1/study-plans` - Create new study plan

### AI Tutor
- `POST /api/v1/ai-tutor/recommendations` - Get personalized recommendations
- `POST /api/v1/ai-tutor/submit` - Submit answer for evaluation
- `POST /api/v1/ai-tutor/chat` - Chat with AI tutor

### Community
- `GET /api/v1/community/posts` - Get community posts
- `POST /api/v1/community/posts` - Create new post
- `POST /api/v1/community/comments` - Add comment to post

### Notifications
- `GET /api/v1/notifications` - Get user notifications
- `POST /api/v1/notifications/mark-read` - Mark notifications as read

## Environment Variables

\`\`\`env
DATABASE_URL=postgresql://user:password@localhost/fschool
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
\`\`\`

## Role-Based Access Control

- **Admin**: Full access to all endpoints and data
- **Parent**: Manage own profile and children's student profiles
- **Student**: Access own data and interact with lessons/AI tutor

## AI Tutor Integration

The AI tutor service is designed to be easily replaceable with actual AI models. Current implementation includes:
- Personalized learning recommendations based on student progress
- Answer evaluation with scoring and feedback
- Interactive chat functionality
- Context-aware responses

## Database Schema

The system includes comprehensive models for:
- Users and Students with role-based relationships
- Progress tracking with weekly records and badges
- Lessons with study plans and completion tracking
- AI tutor sessions and interactions
- Community posts and comments
- Notification system

## Testing

Run tests with:
\`\`\`bash
pytest
\`\`\`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License.
