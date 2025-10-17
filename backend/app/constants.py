from enum import Enum

class ASSESSMENT_SUBJECTS(str, Enum):
    math = "Math"
    science = "Science"
    english = "English"
    humanities = "Humanities"
    entrepreneurship = "Entrepreneurship"

ASSESSMENT_STATUS_PROGRESS = "in_progress"
ASSESSMENT_STATUS_COMPLETED = "completed"
ASSESSMENT_TYPES = ["diagnostic", "formative", "summative"]
TOTAL_QUESTIONS_PER_ASSESSMENT = 20
ASSESSMENT_MAX_QUESTIONS_PER_SUBTOPIC = 5