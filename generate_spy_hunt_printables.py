from pathlib import Path

from pdf_pack import create_printable_pack


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "output" / "FoxGameLab_Spy_Hunt_Printable_Set.pdf"

GAME = {
    "title": "Spy Hunt",
    "mission": "Find the two spies by asking simple questions with the verb to be.",
}

STATE = {
    "topic": "to be",
    "level": "A1",
    "age": "9",
    "skill": "Speaking",
    "duration": "5 min",
}

CARDS = """SET: 6 CARDS

SPY 1
Keep your role secret.
Answer in a full sentence.
Say: No, I am not a spy.
Change one answer after 2 minutes.

SPY 2
Keep your role secret.
Answer in a full sentence.
Say: Yes, I am a student.
Change one detail after 2 minutes.

STUDENT 1
Ask two classmates.
Use: Are you ...?
Listen for a strange answer.
Find the spies.

STUDENT 2
Answer in a full sentence.
Use: Yes, I am. / No, I am not.
Watch for changed details.
Find the spies.

STUDENT 3
Ask: Are you a student?
Ask one follow-up question.
Listen carefully.
Make your guess.

STUDENT 4
Ask and answer clearly.
Use am, is or are.
Write one clue.
Find the spies.
"""

WORKSHEET = """TASK 1 - WARM-UP
1. Say: I am a student.
2. Say: You are my classmate.
3. Ask: Are you a spy?
4. Answer: No, I am not.

TASK 2 - MATCH
1. Are you a student?       A. Yes, they are.
2. Is Max a spy?            B. Yes, I am.
3. Are they ready?          C. No, he is not.
Write: 1 ___   2 ___   3 ___

TASK 3 - CHOOSE AM / IS / ARE
1 I (am / is / are) ready.
2 You (am / is / are) a student.
3 She (am / is / are) not a spy.
4 They (am / is / are) classmates.
5 He (am / is / are) nine.
6 We (am / is / are) detectives.

TASK 4 - ASK AND WRITE
Ask a classmate. Write the short answer.
1. Are you ready? ____________________
2. Are you a student? _________________
3. Are you nine? _____________________
4. Is your friend here? _______________

TASK 5 - MY SUSPECTS
1. Suspect: __________  Why? __________
2. Suspect: __________  Why? __________
3. Watch: ____________________________

TASK 6 - CLUES
1. First clue: _________________________
2. New clue: __________________________
3. Changed answer: ____________________
4. Ask again: _________________________

TASK 7 - FINAL GUESS
1. I think __________ and __________ are spies.
2. Tell your partner your guess.

TASK 8 - WHY?
1. Because __________ said ____________.
2. He / She (is / is not) consistent.
3. They (are / are not) my final suspects.

HELPER BOX
Questions: Are you ...? Is he / she ...?
Answers: Yes, I am. No, I am not.
Report: He / She is ... They are ...

FOX CHALLENGE
1. Ask a new follow-up question with Is or Are.
2. Report two clues in full sentences.
3. Bonus: use am not, is not or are not.
"""

TEACHER_PACK = """START
• Put students in a circle or two small groups.
• Secretly give out 2 SPY and 4 STUDENT cards.
• Say: Ask, listen, find two spies. You have 5 minutes.
Teacher Tip: Model one question and answer before starting.

SAY THIS
• Are you ready to find the spies?
• Ask questions with am, is and are.
• Answer in a full sentence.
• Listen carefully: one answer may change.

ENGLISH SUPPORT
• Are you a student? Yes, I am. / No, I am not.
• Is he/she a spy? Yes, he/she is.
• Are they in your team? Yes, they are.
• I think ___ is a spy because ___.

TEACHER TIPS
• Keep role cards hidden until the final reveal.
• Pair a shy learner with a confident partner.
• Praise clear questions, not only correct guesses.
• Prompt quietly; do not reveal a role.

FOX TWIST
• After 2 minutes, signal the spies discreetly.
• Each spy changes one small identity detail.
• Tell the class: Something may have changed!
Teacher Tip: A changed hobby, age or favourite food works well.

IF TOO EASY
• Allow only two questions per classmate.
• Require one follow-up question.
• Students must explain each guess with because.
• Add a 30-second final decision timer.

IF TOO HARD
• Keep the English Support box visible.
• Let pairs rehearse one question first.
• Accept short answers, then recast the full form.
• Reduce the game to one spy for round one.

AFTER THE GAME
• Reveal the roles and celebrate good detectives.
• Ask: Who were the spies? Which clue helped?
• Invite two learners to report with is / are.
• Correct one common error together.

QUICK CHECK
• Prepare 6 role cards, worksheets and pencils.
• Set a 5-minute timer; keep board markers ready.
• Listen for correct am / is / are questions.
• Check: Can learners answer in a full sentence?
"""


def main() -> None:
    path, pages = create_printable_pack(
        GAME,
        STATE,
        CARDS,
        WORKSHEET,
        TEACHER_PACK,
        output_path=OUTPUT_PATH,
        include_cover=False,
    )
    print(f"pdf_path={path}")
    print(f"pages={pages}")


if __name__ == "__main__":
    main()
