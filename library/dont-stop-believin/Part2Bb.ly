\version "2.25.29"

\header {
  title = "Don't Stop Believin'"
  poet = \markup{"2 — Easy B"\flat" Clarinet/Trumpet"}
}

\score{
  \relative c'{
    \key g \major
    \numericTimeSignature
    \tempo "Rhythmically" 4 = 115
    \override MultiMeasureRest.space-increment = 8
    \override MultiMeasureRest.expand-limit = 3
    \compressMMRests
    R1*8|
    \repeat volta 2{
      d1^\markup{\italic"play second time"}\mf|
      d|
      d|
      c|\break
      d|
      d|
      d|
      c|
      d|
      d|
      d|
      c|\break
      d|
      d|
      d|
      \alternative{
        \volta 1 {c}
        \volta 2 {c}
      }
    }
    \repeat volta 2{
      d4.\f c8-> r2|
      d4. e8-> r2|
      a,4. b8-> r2|
      a4. b8-> r2|
      d4. c8-> r2|
      \alternative{
       \volta 1 {
       d4.\f e8-> r2|
       a,4. b8-> r2|
      a4. b8-> r2|}
       \volta 2{
       d4. e8-> r2\break }
      }
    }
    d1~|
    d \bar "||"
        \override MultiMeasureRest.space-increment = 12
\compressMMRests
    R1*8|
    \repeat volta 2{
      d1\f|
      d|
      g|\break
      c,|
      d|
      d|
      d|
      e2 r|
    }
    r1 \bar"|."
  }
  
}