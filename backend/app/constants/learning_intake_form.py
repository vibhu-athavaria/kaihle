INTAKE_FORM_JSON = {
  "form_id": "kaihle_learning_profile_intake_v1",
  "target_age_range": "8-18",
  "sections": [
    {
      "section_id": "learning_conditions",
      "title": "How You Like to Learn",
      "description": "These questions help us present lessons in a way that feels comfortable and effective for you.",
      "questions": [
        {
          "question_id": "instructional_support",
          "type": "multi_select",
          "label": "When learning something new, what usually helps you most?",
          "max_selections": 2,
          "options": [
            { "value": "step_by_step", "label": "Clear step-by-step explanations" },
            { "value": "worked_examples", "label": "Examples before trying on my own" },
            { "value": "short_chunks", "label": "Short explanations with practice in between" },
            { "value": "exploration", "label": "Exploring and figuring things out myself" },
            { "value": "guided_support", "label": "Someone checking in and guiding me" }
          ]
        },
        {
          "question_id": "attention_span",
          "type": "single_select",
          "label": "How long can you usually focus on a lesson without a break?",
          "options": [
            { "value": "lt_10", "label": "Less than 10 minutes" },
            { "value": "10_20", "label": "10–20 minutes" },
            { "value": "20_30", "label": "20–30 minutes" },
            { "value": "gt_30", "label": "More than 30 minutes" }
          ]
        }
      ]
    },
    {
      "section_id": "accessibility_needs",
      "title": "Learning Comfort & Accessibility",
      "description": "This is not a diagnosis. It only helps us present learning materials more comfortably.",
      "questions": [
        {
          "question_id": "learning_difficulties",
          "type": "multi_select",
          "label": "Have you ever been told you have, or do you experience difficulty with:",
          "options": [
            { "value": "reading_text", "label": "Reading long texts" },
            { "value": "spelling_decoding", "label": "Spelling or decoding words" },
            { "value": "sustained_attention", "label": "Paying attention for long periods" },
            { "value": "auditory_memory", "label": "Remembering spoken instructions" },
            { "value": "visual_sensitivity", "label": "Sensitivity to bright screens or visual clutter" },
            { "value": "none", "label": "None of the above" },
            { "value": "prefer_not_to_say", "label": "Prefer not to say" }
          ]
        }
      ]
    },
    {
      "section_id": "interests_motivation",
      "title": "What Interests You",
      "questions": [
        {
          "question_id": "interest_themes",
          "type": "multi_select",
          "label": "Which topics or themes interest you the most?",
          "max_selections": 3,
          "options": [
            { "value": "games_puzzles", "label": "Games & puzzles" },
            { "value": "nature_animals", "label": "Nature & animals" },
            { "value": "technology_ai", "label": "Technology & AI" },
            { "value": "stories_characters", "label": "Stories & characters" },
            { "value": "real_world_problems", "label": "Real-world problems" },
            { "value": "art_design", "label": "Art & design" },
            { "value": "history_cultures", "label": "History & cultures" }
          ]
        }
      ]
    },
    {
      "section_id": "expression_preferences",
      "title": "How You Like to Show Learning",
      "questions": [
        {
          "question_id": "demonstrate_learning",
          "type": "multi_select",
          "label": "How do you like to show what you’ve learned?",
          "options": [
            { "value": "answer_questions", "label": "Answering questions" },
            { "value": "explain_own_words", "label": "Explaining in my own words" },
            { "value": "create_artifact", "label": "Creating something (poster, slides, story)" },
            { "value": "solve_problems", "label": "Solving problems" },
            { "value": "talk_it_through", "label": "Talking it through" }
          ]
        }
      ]
    }
  ]
}
