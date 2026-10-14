# Kaihle Privacy Policy (DRAFT)

> **DRAFT. Not legal advice. Not for publication.** Written by engineering from what the code does on 2026-10-11, for review by Kaihle's legal counsel or data-protection officer. Every sentence that makes a legal commitment or claim is marked **[COUNSEL REVIEW]**. Square-bracket placeholders must be filled by Kaihle. Statements about what the software does were checked against the code (see `DATA_INVENTORY.md` and `LLM_DATA_FLOWS.md`); where the software does not yet do what a sentence promises, the sentence is marked **[NOT YET TRUE]** and listed in `GAPS.md`.

**Effective date:** [DATE]
**Who we are:** [LEGAL ENTITY NAME AND ADDRESS: TO BE COMPLETED BY KAIHLE] ("Kaihle", "we"). **[COUNSEL REVIEW: which entity is controller and which is processor, per school and per country.]**
**Contact for privacy questions:** [PRIVACY CONTACT EMAIL: TO BE COMPLETED BY KAIHLE]
**Data protection officer or representative, if required:** [TO BE COMPLETED BY KAIHLE] **[COUNSEL REVIEW]**

---

## 1. What this policy is for

Kaihle is a learning tool used by schools. It helps teachers see where students need help and gives students explanations and practice. This policy explains what information we collect, why, who can see it, and what choices you have.

It is written for school leaders, teachers, parents and students. Students are aged 11 to 18. We have tried to use plain words. **[COUNSEL REVIEW: age-appropriate versions and translation for each pilot country.]**

Kaihle is used through a school. In most cases the school decides to use Kaihle and tells us who its users are. **[COUNSEL REVIEW: whether the school or Kaihle is responsible for choosing why and how the data is used, and what each must tell families.]**

## 2. What we collect

**About every user**
- Name, school email address (if the school gives one), a username (if used), role (student, teacher, school admin, parent), the school they belong to, and when they last signed in.
- A password. We store only a scrambled version (a hash), never the password itself.

**About students**
- Grade and age. We do not store a date of birth.
- Class membership.
- A short learning-style questionnaire. We keep the scores we work out from it (for example, whether a student learns best by seeing or by doing), the work-style preferences, and the interests the student picked from a list. We do not keep the individual answers.
- Answers to assessments, how long they took, scores, and which topics they find hard or easy.
- Progress in mini-courses, and thumbs-up or thumbs-down feedback. If a student types a comment with feedback, we keep it.
- **What a student types to the AI tutor**, and the tutor's replies. Chat history is kept for each topic.
- **Written answers to open questions** in mini-courses, and the feedback they received.

**About teachers and school staff**
- Class and lesson-plan information, content they write or edit, and questions they submit for review. Optional profile details such as qualifications and a short bio.

**About parents**
- Their name, email, and the link to their child. In the current version a parent does not set a password.

**About the school**
- School name, address, city, country, contact details, and subscription and invoice information. We do not store payment-card numbers in the application database. **[COUNSEL REVIEW: confirm with the payment arrangements actually in use.]**

**Technical information**
- Our servers record each request (which page, when, which account ID, how long it took). Some of our logs currently include email addresses. **[NOT YET TRUE that logs contain no personal data; see GAPS G-8.]**
- A record of each call we make to an AI provider, including its cost and, when this setting is switched on, **the full text we sent and received** (see section 5).

## 3. Why we use it

- To run the service: sign people in, show the right classes and content, and keep each school's data separate.
- To show teachers and school leaders where students need support.
- To personalise explanations and practice to a student's learning style and interests.
- To mark open written answers and give feedback.
- To help teachers prepare lesson plans.
- To keep the service safe, fix problems, and measure what the AI features cost.
- To check the quality of the AI features (section 7).
- We do not sell personal data and we do not use it for advertising. **[COUNSEL REVIEW: confirm these statements are accurate for the business model.]**

**[COUNSEL REVIEW: the lawful basis for each purpose in each country, including consent where required for children.]**

## 4. Who can see it

- **Students** can see their own work and chat.
- **Teachers** can see the progress and results of students in their own classes.
- **School administrators** can see data for their own school only. The software is designed so one school cannot see another school's data; cross-school requests are refused. **[COUNSEL REVIEW]** (Do not describe this as a guarantee; see `DATA_INVENTORY.md` section 6.)
- **Parents** can see information about their own child through the parent view.
- **Kaihle's administrator** (a small number of named people at Kaihle) can see data across schools in order to run, support and fix the service. This includes the AI call log with full text (section 5). Support staff can also sign in as a user to help them; **[NOT YET TRUE: confirm this access is recorded and reviewed; see GAPS G-16.]**
- **Service providers** that help us run Kaihle (section 6).
- We may disclose information if the law requires it. **[COUNSEL REVIEW]**

Teachers and school administrators do **not** see the AI call log, and do not take part in reviewing it.

## 5. How we use AI, and what it means for children's text

Kaihle uses AI language models. They are run by **third-party AI providers** that we choose and may change: [LIST OF AI PROVIDERS, REGIONS AND TERMS: TO BE COMPLETED BY KAIHLE FROM `LLM_DATA_FLOWS.md` SECTION 5]. **[COUNSEL REVIEW: disclosure of provider names and regions to schools and parents.]**

**What is sent to an AI provider**
- When a student asks the AI tutor a question, **the words they typed, and up to the last ten messages in that conversation, are sent to an AI provider** to produce the reply.
- When a student answers an open written question, **their written answer** is sent to an AI provider so that it can be marked.
- When a student asks for an explanation, we send the topic, the student's learning style, up to two interests, and any question they typed.
- When we create a practice question for a student, we send the topic and the student's learning style and interests.
- When a teacher asks for a lesson plan, we send the class name, subject, grade, topics, the school's city and country, the number of students, and **class averages** for learning styles and the most common interests. We do not send student names or individual results.
- For content that is the same for everyone (for example a model explanation of a topic), no student information is sent.

**What we do not send**
- We do not send student names, email addresses, usernames or student ID numbers as separate fields. **But we do not remove personal details that a student types themselves.** If a child writes their name, school, or something about their life into the tutor, it goes to the provider. **[COUNSEL REVIEW: whether this is acceptable without filtering, and what warning to show students.]** **[NOT YET TRUE: students are not currently warned in the app; see GAPS G-3.]**

**What the AI providers do with it**
- [PROVIDER TERMS ON RETENTION AND TRAINING USE: TO BE COMPLETED BY KAIHLE AFTER REVIEWING EACH CONTRACT] **[COUNSEL REVIEW]**
- We will only use providers whose terms do not allow them to train their models on our data. **[NOT YET TRUE and cannot be promised until each provider's terms are checked. Do not publish this sentence as written.]**

**What we keep about AI calls**
- When logging is on, we keep the **full text** sent to and received from the provider, for Kaihle's administrator to review problems and cost. It does not carry a student's name as a field, but the text itself can identify a child. Kaihle's administrator is the only role that can open it. We do not currently delete it automatically. **[NOT YET TRUE that it is deleted after a set time; see GAPS G-1. Retention period: [TO BE DECIDED BY KAIHLE] COUNSEL REVIEW.]**

**AI can be wrong.** Explanations, questions and marks produced by AI may contain mistakes. Teachers remain responsible for decisions about students. Kaihle does not make automated decisions about grades, placement or discipline. **[COUNSEL REVIEW: confirm no automated decision-making obligations are triggered; confirm that statement stays true as features change.]**

Our content is described as curriculum-informed. Schools are responsible for the curriculum they follow and for any examination arrangements.

## 6. Service providers (subprocessors)

We use other companies to run Kaihle. Full list, regions and terms: [TO BE COMPLETED BY KAIHLE FROM `LLM_DATA_FLOWS.md` SECTION 5]. By kind, they are:
- AI language-model and embedding providers (section 5).
- A hosting and database provider (the pilot plan uses Render.com and a managed PostgreSQL database).
- An email delivery service, used to send sign-in links, password resets and notices. Some emails include the recipient's first name and school name. School-created accounts are sent a temporary password in the email. **[NOT YET TRUE that we avoid sending passwords by email; see GAPS G-9.]**
- A video search service (YouTube) to find educational videos. No student data is sent for this.
- Students watch embedded YouTube videos, and the apps load fonts from a web-font service. Those services can see a visitor's IP address and may set cookies. **[COUNSEL REVIEW: cookie and tracking notice, and children's use of embedded video.]**

**[COUNSEL REVIEW: processor agreements with each provider.]**

## 7. Using real usage to check AI quality

We check that our AI features work well by looking at a **small sample** of real AI outputs. We do this under these rules:

1. **Only Kaihle's administrator** takes part. **No teacher, school administrator or parent reviews it.**
2. **Personal details are removed first.** Before any text is sent for checking, we automatically remove email addresses, phone numbers, web links, long ID-like numbers, and the names of people and the school. This is a best-effort tool. It **cannot reliably find** places, relatives' names or personal circumstances that a child writes in their own words. If removal fails for an item, that item is skipped and never sent. **[COUNSEL REVIEW: wording of the limits.]**
3. **Sampling is small, random and limited in time**, and it is off until Kaihle's administrator turns it on, task by task, with a budget.
4. **Student-written text is a separate, extra step.** Checking outputs that contain what students typed (the tutor, written-answer marking and explanation features) is only allowed after this policy has been approved, and only after the administrator records that they accept the extra risk.
5. **The results contain no text.** We store only pass or fail figures and the ID of the original record, never a copy of what a student wrote.
6. The checking uses an AI provider that is different from the one that produced the output, and its terms must be reviewed first. [JUDGE PROVIDER, TERMS: TO BE COMPLETED BY KAIHLE]

**[NOT YET TRUE: the production sampling described here is designed (task T18) but not yet built. This section must not be published until it is, or must be reworded as "planned". See GAPS G-6.]** **[COUNSEL REVIEW: whether this use needs a separate notice, a new lawful basis, or school consent.]**

## 8. Children

Kaihle is used by students aged 11 to 18 through their school. **[COUNSEL REVIEW: local age-of-consent thresholds in each country, parental consent or school authority for under-age users, and who gives it.]**

- We collect only what the learning features need.
- We do not show advertising to students and do not build advertising profiles. **[COUNSEL REVIEW]**
- Parents and schools can ask us about their child's data (section 10).
- We do not show students a notice or ask for consent at first sign-in. **[NOT YET TRUE that students or parents receive a notice; see GAPS G-5.]**

## 9. How long we keep it

We have **not yet set final retention periods**. Proposed periods are in `RETENTION_AND_EVALUATION.md` and need a decision. **[PROPOSED. Insert final table here after Kaihle's decision. COUNSEL REVIEW.]**

Today the software does not automatically delete any personal data after a set time. **[NOT YET TRUE for any automatic deletion; see GAPS G-1 and G-2.]**

## 10. Your choices and rights

Depending on where you live, you may be able to ask to see, correct, export or delete your information, or to object to how it is used. **[COUNSEL REVIEW: the rights that apply in each pilot country, how to verify a parent or child, response time, and who answers requests (Kaihle or the school).]**

To make a request, contact [PRIVACY CONTACT: TO BE COMPLETED BY KAIHLE]. Schools can also make requests on behalf of their students. **[NOT YET TRUE that there is a self-service way to export or delete a user's data; today it would be done by hand by an engineer. See GAPS G-2.]**

## 11. Security

- Passwords are stored as hashes. Sign-in uses short-lived tokens. Access is limited by role and school.
- Data is sent over encrypted connections. **[COUNSEL REVIEW and engineering confirmation of the deployed configuration.]**
- No system is perfectly secure. We will tell schools about a data breach as the law requires. **[COUNSEL REVIEW: notice duties, timeframes, contacts. A breach response procedure is not in the repository; see GAPS G-17.]**

## 12. Where data is stored and sent

Our servers and our providers' servers may be in different countries. [HOSTING AND PROVIDER REGIONS: TO BE COMPLETED BY KAIHLE] **[COUNSEL REVIEW: transfers out of each pilot country and the basis for them.]**

## 13. Changes to this policy

We will update this page when our practices change and tell schools about important changes. **[COUNSEL REVIEW: notice period and how changes are communicated to families.]**

---

### Drafting notes (delete before publishing)

1. Section 5 and 7 must be re-checked against `LLM_DATA_FLOWS.md` whenever a prompt template, call site or router task changes.
2. Do not add any sentence saying Kaihle meets or satisfies a named law until counsel has signed off in writing.
3. The phrase "curriculum-informed" is deliberate (CONSTITUTION Rule 23). Do not add statements about approval by any examination body.
