\version "2.25.29"
\header {
  title = "Old Macdonald had a Band"
  subtitle = "(First Section Feature)"
  composer = "Arranged by John Higgins"
  tagline = ""
  poet = "Trumpet"
}

\score{
  \relative c'{
    \numericTimeSignature
    \compressMMRests{
      \override MultiMeasureRest.expand-limit = 1
      \override MultiMeasureRest.space-increment = 8
      f4^"March Tempo" f f c|
      d
      d
      c2|
      a'4 a g g|
      f2 r4 c|
      f f f c|\break
      d d c2|
      a'4 a g g |
      f2 r4 c \mark \markup \box "9"|
      f f f2|
      f4 f f2|
      f4 f f f|\break
      f2 f|
      f4 f f c|
      d d c2|
      a'4 a g g|
      f2 r |\mark \markup \box "17"
      R1*2|\break
      f4 f f f|
      f2 f|
      f4 f f c|
      d4 d c2|
      a'4 a g g |
      f2 r|\mark \markup \box "25"\break
      R1*4
      f4 f f f|
      f2 f|
      f4 f f c|
      d d c2|
      a'4 a g g|
      f2 r |\mark \markup \box "35"\break
      R1*6
      f4 f f f|
      f2 f|\mark \markup \box "43"
      f4 f f c|\break
      d d c2|
      a'2 a |
      g g|
      f1|
      f4 c f r4 \bar"|."
    }
  }
 
}