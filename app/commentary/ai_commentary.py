def generate(ball):
    if ball.runs==6:
        return "Huge SIX!"
    if ball.runs==4:
        return "Beautiful boundary"
    if ball.is_wicket:
        return "Wicket!"
    return "Dot ball"
