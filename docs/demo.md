# Recorded offline demo

Recorded from the local FastAPI server on 2026-11-10, using the generated synthetic fixture. No provider calls or cloud credentials were used.

Start the backend using the README, then reproduce each request with `POST http://127.0.0.1:8000/query`, `Content-Type: application/json`, and the JSON body shown below. If an API access token is configured, include its Bearer header. These responses demonstrate the backend, not a hosted service.

## Show students with attendance below 60%

Request:

```json
{
  "query": "Show students with attendance below 60%",
  "llm_config": {
    "strategy": "offline"
  }
}
```

Actual response:

```json
{
  "answer": "1. Id: 24 | Name: Neha Mishra | Branch: CE | Year: 4 | Percentage: 38.7\n2. Id: 15 | Name: Karan Malhotra | Branch: ME | Year: 1 | Percentage: 42.8\n3. Id: 5 | Name: Vikram Reddy | Branch: CSE | Year: 3 | Percentage: 45.2\n4. Id: 21 | Name: Manav Kapoor | Branch: CE | Year: 2 | Percentage: 47.9\n5. Id: 12 | Name: Meera Bhat | Branch: ECE | Year: 3 | Percentage: 49.3\n6. Id: 17 | Name: Amit Tiwari | Branch: ME | Year: 3 | Percentage: 53.6\n7. Id: 3 | Name: Rohan Mehta | Branch: CSE | Year: 2 | Percentage: 55.0\n8. Id: 10 | Name: Diya Verma | Branch: ECE | Year: 2 | Percentage: 58.4",
  "explanation": "Queried the attendance table for students with attendance < 60.0%. Found 8 student(s) matching this criteria.",
  "query_type": "data",
  "data": [
    {
      "id": 24,
      "name": "Neha Mishra",
      "branch": "CE",
      "year": 4,
      "percentage": 38.7
    },
    {
      "id": 15,
      "name": "Karan Malhotra",
      "branch": "ME",
      "year": 1,
      "percentage": 42.8
    },
    {
      "id": 5,
      "name": "Vikram Reddy",
      "branch": "CSE",
      "year": 3,
      "percentage": 45.2
    },
    {
      "id": 21,
      "name": "Manav Kapoor",
      "branch": "CE",
      "year": 2,
      "percentage": 47.9
    },
    {
      "id": 12,
      "name": "Meera Bhat",
      "branch": "ECE",
      "year": 3,
      "percentage": 49.3
    },
    {
      "id": 17,
      "name": "Amit Tiwari",
      "branch": "ME",
      "year": 3,
      "percentage": 53.6
    },
    {
      "id": 3,
      "name": "Rohan Mehta",
      "branch": "CSE",
      "year": 2,
      "percentage": 55.0
    },
    {
      "id": 10,
      "name": "Diya Verma",
      "branch": "ECE",
      "year": 2,
      "percentage": 58.4
    }
  ],
  "model_info": {
    "provider": "database",
    "model": "SQLite",
    "token_count": 0
  },
  "error": false
}
```

## Analyze performance of CSE 3rd year students

Request:

```json
{
  "query": "Analyze performance of CSE 3rd year students",
  "llm_config": {
    "strategy": "offline"
  }
}
```

Actual response:

```json
{
  "answer": "[ANALYSIS] Performance Analysis (Students in CSE branch year 3):\n\n  * Students analyzed: 2\n  * Average marks: 64.3\n  * Highest avg: 87.0\n  * Lowest avg: 41.7\n  * Average attendance: 67.0%\n  * Students with attendance < 60%: 1\n\n  [!] 1 student(s) need attention:\n    - Vikram Reddy: attendance 45.2%, avg marks 41.7",
  "explanation": "Analysis performed using rule-based engine. Analyzed 2 student records from: Students in CSE branch year 3. Thresholds used: attendance < 60% (flagged), avg marks < 50 (flagged).",
  "query_type": "analytical",
  "data": [
    {
      "id": 6,
      "name": "Sneha Gupta",
      "branch": "CSE",
      "year": 3,
      "attendance": 88.7,
      "avg_marks": 87.0
    },
    {
      "id": 5,
      "name": "Vikram Reddy",
      "branch": "CSE",
      "year": 3,
      "attendance": 45.2,
      "avg_marks": 41.7
    }
  ],
  "model_info": {
    "provider": "fallback",
    "model": "rule-based",
    "token_count": 165
  },
  "error": false
}
```

## What is the minimum attendance policy?

Request:

```json
{
  "query": "What is the minimum attendance policy?",
  "llm_config": {
    "strategy": "offline"
  }
}
```

Actual response:

```json
{
  "answer": "1. ATTENDANCE POLICY\n--------------------\n- Minimum required attendance: 75% per semester.\n- Students with attendance below 75% will receive a warning notice.\n- Students with attendance below 60% will be marked as \"detained\" and may\n  not be allowed to sit for end-semester examinations.\n- Medical leave of up to 10 days per semester is allowed with valid\n  documentation from a registered medical practitioner.\n- Students with attendance between 60-75% may apply for condonation with\n  a fine of Rs. 500 per subject.\n\n2. EXAMINATION ELIGIBILITY\n--------------------------\n- Students must have a minimum of 75% attendance to be eligible for\n  end-semester examinations.\n- Students must have submitted all mandatory assignments and lab work.\n- Students with pending disciplinary actions may be barred from exams.\n- Re-examination is allowed once per subject per semester with a fee of\n  Rs. 1000.\n\n2. REMEDIAL CLASSES\n-------------------\n- Remedial classes are offered for students scoring below 50% in any subject.\n- Schedule: Extra classes held on Saturdays, 10 AM — 1 PM.\n- Attendance in remedial classes is mandatory for eligible students.\n- Topics covered: Fundamentals review, problem-solving workshops, and\n  doubt-clearing sessions.\n- Faculty mentors are assigned to each weak student for personalized guidance.\n\n3. IMPROVEMENT EXAMINATIONS\n----------------------------\n- Students who have passed but wish to improve their grades may appear for\n  improvement exams in the subsequent semester.\n- Maximum of 3 subjects can be attempted for improvement per semester.\n- The better of the two scores (original or improvement) will be considered.\n- Fee for improvement exam: Rs. 500 per subject.\n\n4. WEAK STUDENT IDENTIFICATION CRITERIA\n----------------------------------------\n- A student is classified as \"academically weak\" if:\n  * Average marks across all subjects < 50%, OR\n  * Attendance percentage < 60%, OR\n  * Failed in 2 or more subjects in a single semester.\n- Interventions for weak students:\n  * Mandatory remedial classes\n  * Bi-weekly mentor meetings\n  * Peer tutoring program (pairing with high performers)\n  * Progress tracking with monthly reports to parents/guardians\n\n5. SUGGESTIONS FOR IMPROVEMENT\n-------------------------------\n- Regular study schedule: Minimum 2 hours of self-study daily.\n- Active participation in class discussions and group projects.\n- Utilize college resources: library, online databases, lab facilities.\n- Seek help early: approach faculty during office hours for doubts.\n- Form study groups with classmates for collaborative learning.\n- Practice previous years' question papers for exam preparation.\n- Maintain a healthy work-life balance: exercise, sleep, nutrition.\n\n6. BRANCH-SPECIFIC GUIDELINES\n------------------------------\n- CSE: Focus on programming practice (minimum 2 coding problems/day).\n  Participate in hackathons and open-source contributions.\n- ECE: Emphasize lab work and circuit design projects. Join electronics\n  clubs for hands-on experience.\n- ME: Focus on workshop skills and CAD software proficiency. Participate\n  in design competitions and internships.\n- CE: Emphasize site visits and practical knowledge. Study building codes\n  and structural analysis thoroughly.\n\n7. MENTORSHIP PROGRAM\n---------------------\n- Every student is assigned a faculty mentor at the start of each year.\n- Mentor meetings: At least once per month (mandatory).\n- Mentors track academic progress, attendance, and overall well-being.\n- Students can request a change of mentor through the Dean's office.",
  "explanation": "No LLM available for synthesis. Showing matched passages from sample documents based on keyword relevance.",
  "query_type": "knowledge",
  "data": [],
  "model_info": {
    "provider": "fallback",
    "model": "keyword-search",
    "token_count": 983
  },
  "error": false
}
```
