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

# Learning Profile Constants
INTEREST_CATEGORIES = [
    "Sports (Basketball, Soccer, Tennis, etc.)",
    "Music",
    "Gaming (Video games, Board games)",
    "Cooking/Food",
    "Art/Drawing",
    "Technology/Coding",
    "Animals/Nature",
    "Fashion",
    "Cars/Vehicles",
    "Movies/TV Shows",
    "Reading/Books",
    "Dance",
    "Space/Astronomy",
    "Magic/Tricks",
    "Superheroes",
    "Robots",
    "Dinosaurs",
    "Mysteries/Detective work",
    "Building/Construction",
    "Photography",
    "Writing/Stories",
    "Science Experiments",
    "Travel/Exploring",
    "Gardening",
    "Pets",
    "Collecting (stamps, cards, etc.)",
    "Martial Arts",
    "Theater/Acting",
    "Instruments (piano, guitar, etc.)",
    "Crafts",
    "Swimming",
    "Cycling",
    "Hiking/Outdoor activities",
    "Other"
]

PREFERRED_FORMATS = [
    "Video",
    "Text",
    "Interactive",
    "Audio"
]

PREFERRED_SESSION_LENGTHS = [15, 30, 45, 60]

# Payment Plan Types
PAYMENT_PLAN_BASIC = "basic"
PAYMENT_PLAN_PREMIUM = "premium"

# Billing Constants
DEFAULT_TRIAL_PERIOD_DAYS = 15
DEFAULT_YEARLY_DISCOUNT_PERCENTAGE = 20.00
BILLING_CYCLE_MONTHLY = "monthly"
BILLING_CYCLE_ANNUAL = "annual"

# Subscription Plan Constants
BASIC_PLAN_PRICE_PER_SUBJECT = 25.00  # $25 per subject per month
PREMIUM_PLAN_PRICE = 85.00  # $85 per month for all subjects