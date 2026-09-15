#set page(
paper: "a4",
margin: (left: 25mm, right: 20mm, top: 25mm, bottom: 25mm),
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)

#let at(x, y, body) = place(top + left, dx: x - 25mm, dy: y - 25mm, body)

#at(20.0mm, 8mm, block(width: 170mm, text(size: 10pt)[
Marie Skłodowska Curie\
Laboratory of Physics and Chemistry\
Sorbonne University\
75005 Paris, France]))

#at(20mm, 45mm, block(width: 85mm, height: 45mm, inset: (left: 0mm))[
#block(width: 100%, height: 5mm, align(bottom + left, text(size: 7pt)[
#underline[Laboratory of Physics and Chemistry, Sorbonne Univ., Paris]]))
#v(2.5mm)
Leonardo da Vinci\
Casa di Leonardo\
Near the Church of Santa Croce\
Florence, Republic of Florence (c. 1500)])

#place(top + right, dy: 98.5mm - 25mm, [July 14, 1903])

#v(83.5mm)

Dear Maestro Leonardo

#ts-callout-style.update("fancy")

I have received your latest letter—delivered, I assume, by whatever ingenious flying
machine you are currently testing—and feel compelled to clarify a few scientific
misunderstandings before you accidentally remove yourself from the timeline.

First, while your enthusiasm for "radiant essences" is admirable, radioactivity is
not a universal power source. Your idea for a "self-illuminating mechanical bird,
animated by glowing stones" is creative, but such stones would send you flying only
toward the afterlife. Please wear gloves—preferably very thick ones.

Second, I examined the sketch you enclosed, a contraption somewhere between a windmill,
a cauldron, and an umbrella. I cannot determine its purpose, but I urge caution. If it
is meant to rotate, do not sit inside it. If it is meant to boil, do not sit inside it.
If it is meant to do both… absolutely do not sit inside it.

Lastly, you asked whether radioactive materials might accelerate human creativity.
A flattering thought, but the glow around me is scientific, not – as you
suggested – "proof of a supernatural muse." Should you begin to glow,
I advise stepping away quickly.

I remain deeply impressed by your mind, your sketches, and your relentless curiosity.
Should you need help with physics—or with identifying substances that should not go
into flying machines—I remain at your service.

With great scientific affection,

#v(0.8em)
#image("marie-curie.svg", height: 1.6cm)

Marie Skłodowska Curie

#v(1em)
PS: How did you manage to withstand the ravages of time?
You should have been dead for 384 years by now.
