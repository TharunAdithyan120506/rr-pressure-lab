# Share your journey

> One paragraph on the week behind this submission — for the optional "share your journey" section.

I spent a week on this, and most of it went on a question I did not expect to be hard: what actually
*is* pressure? My first instinct was the obvious one — the last few overs of a close chase — but the
moment I scored every ball by how much the result could swing on it, the data pushed back. Nearly a
third of the highest-leverage deliveries in five years of cricket turn out to be in the *powerplay*
of a chase, where two early wickets quietly decide a game nobody remembers as tense. That one finding
rebuilt the whole project. From there it became a loop I genuinely enjoyed: build a win-probability
model, watch it get a famous finish wrong, dig into why, fix it, run it again. The 2023 IPL final
peaking at four-needed-off-one was the moment it clicked. The hardest lesson came late, though, and
it was a humbling one — when I tested whether "clutch" repeats, it barely did. Ranking players purely
on their pressure balls produced a list that fell apart the moment I split the data in half. I could
have ignored that and shipped a spicier top ten. Instead I rebuilt the rating to borrow from every
ball a player has faced, and wrote the uncomfortable conclusion into the report itself: being good
under pressure is mostly just being good, and the players worth trusting are the excellent ones who
don't shrink. A week in, the thing I'm proudest of isn't the model — it's that the report says where
it's wrong.
