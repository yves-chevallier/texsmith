\ProvidesClass{mkbook}[2024/09/26 MkDocs class]
\LoadClass[9pt,twoside]{memoir}

\RequirePackage{fontspec}
\RequirePackage[svgnames,dvipsnames,x11names]{xcolor}
\RequirePackage{tikz}
\RequirePackage{textcomp} % For ©, ™
\RequirePackage{amsmath} % For \text
\RequirePackage{amssymb} % For √, ∞, etc.
\RequirePackage{gensymb} % For °, ℃, ℉, etc.
\RequirePackage{nicefrac}
\RequirePackage{fancyhdr}
\RequirePackage[normalem]{ulem}
\RequirePackage{graphicx}
\RequirePackage{unicode-math}
\RequirePackage{fontawesome5}
\RequirePackage{multicol}
\RequirePackage{stackengine}
\RequirePackage{booktabs}
\RequirePackage{minted}
\RequirePackage[many,minted]{tcolorbox}
\RequirePackage{callouts}
\RequirePackage{todolist}
\RequirePackage{keystroke}
\RequirePackage{csquotes}
\RequirePackage{epigraph}
\RequirePackage{capt-of}
\RequirePackage[acronym,xindy]{glossaries}
\RequirePackage{imakeidx}
\RequirePackage{fvextra}
\RequirePackage{titlesec}
\RequirePackage{enumitem}
\RequirePackage{etoolbox}
\RequirePackage{tocloft}
\RequirePackage{adjustbox}
\RequirePackage{progressbar}
\RequirePackage{caption}
\RequirePackage{microtype}
\RequirePackage[\VAR{language|default('english')}]{babel}
\RequirePackage{emptypage}

\definecolor{linkcolor}{RGB}{34, 18, 104}
\definecolor{urlcolor}{RGB}{104, 18, 55}

\RequirePackage[
  colorlinks=true,
  plainpages=true,
  linkcolor=black,
  citecolor=black,
  plainpages=false,
  unicode=true,
  urlcolor=urlcolor]{hyperref}

\RequirePackage[
  paperwidth=160mm,
  paperheight=240mm,
  top=20mm,
  bottom=20mm,
  left=20mm,
  right=15mm,
  headheight=6mm,
  headsep=5mm,
  marginparsep=4mm,
  heightrounded]{geometry}

\usetikzlibrary{shapes.geometric}
\usetikzlibrary{calc}
\usetikzlibrary{shadows}

%
% Fonts
%

% Set fallback fonts
\directlua{luaotfload.add_fallback
  ("fontfallback",
  {
      "NotoColorEmoji:mode=harf;",
      "NotoNaskhArabic:mode=harf;",
      "NotoSerifHebrew:mode=harf;",
      "NotoSerifDevanagari:mode=harf;",
      "NotoSerifTamil:mode=harf;",
      "NotoSerifTibetan:mode=harf;",
      "NotoSerifCJKkr:mode=harf;",
      "NotoSans:mode=harf;",
      "NotoSansSymbols2-Regular:mode=harf;",
      "NotoSansMath-Regular:mode=harf;",
      "NotoMusic-Regular:mode=harf;",
      "NotoSansSyriac:mode=harf;",
      "NotoSansSyriacWestern:mode=harf;"
    }
  )}

\setmainfont{Latin Modern Roman}[
  RawFeature={fallback=fontfallback}
]

\setsansfont{Latin Modern Sans}[
  RawFeature={fallback=fontfallback}
]

\setmonofont{FreeMono}[
  Scale=0.9,
  ItalicFont={* Oblique},
  BoldFont={* Bold},
  BoldItalicFont={* Bold Oblique},
  RawFeature={fallback=fontfallback}
]

\graphicspath{{assets/}}

%
% Adjust spacing
%

% Prevent too many overful \hbox (with some fonts)
\tolerance=2000
\emergencystretch=10pt

% Give more spaces on Table of content (between numbers and text)
\setlength{\cftpartnumwidth}{4em}
\setlength{\cftsectionnumwidth}{3em}
\setlength{\cftsubsectionnumwidth}{3.5em}
\setlength{\cftfigurenumwidth}{3em}
\setlength{\cfttablenumwidth}{3em}

\captionsetup[table]{skip=10pt}

% Make quotations italic and smaller
\AtBeginEnvironment{displayquote}{\small\itshape}

% Fit table to page width
\let\oldtabular\tabular
\let\endoldtabular\endtabular

\newsavebox{\mytablebox}
\renewenvironment{tabular}[1]
  {\begin{lrbox}{\mytablebox}\small\oldtabular{#1}} % Temporary box to store table
  {\endoldtabular\end{lrbox}%
   \ifdim\wd\mytablebox>\linewidth
     \resizebox{\linewidth}{!}{\usebox{\mytablebox}} % Adjust to fit line width
   \else
     \usebox{\mytablebox} % Otherwise, use the table as is
   \fi
  }

% Custom epigraph style
\setlength\epigraphwidth{.8\textwidth}
\setlength\epigraphrule{0pt}

%
% Headers and footers
%

% No line on the footer
\renewcommand{\footrulewidth}{0pt}

% Part head pages
\fancypagestyle{part}{%
  \fancyhf{}
  \renewcommand{\headrulewidth}{0pt}
}

% Chapter head pages
\fancypagestyle{plain}{%
  \fancyhf{}
  \renewcommand{\headrulewidth}{0pt}
  \fancyfoot[LE,RO]{\thepage}
}

% Mainmatter regular page style
\fancypagestyle{fancy}{%
  \fancyhf{}
  \renewcommand{\headrulewidth}{0.5pt}
  \fancyhead[LE]{\leftmark}
  \fancyhead[RO]{\rightmark}
  \fancyfoot[LE,RO]{\thepage}
}

% Associate the part page style to the part
\patchcmd{\part}{\thispagestyle{plain}}{\thispagestyle{part}}{}{}

\newcommand{\changelocaltocdepth}[1]{%
  \addtocontents{toc}{\protect\setcounter{tocdepth}{#1}}%
  \setcounter{tocdepth}{#1}%
}

\apptocmd{\frontmatter}{%
  \pagestyle{plain}%
  \changelocaltocdepth{1}%
  \setcounter{secnumdepth}{0}
}{}{}

\apptocmd{\mainmatter}{%
  \pagestyle{fancy}%
  \changelocaltocdepth{2}%
  \setcounter{secnumdepth}{2}
}{}{}


%
% Listing / Code configuration
%

\usemintedstyle{bw}

\newtcblisting[auto counter,number within=section,
  list inside=mypyg]{code}[4][]{%
  breakable,
  listing only,
  enhanced,
  colback=white,
  pad at break*=1mm,
  toptitle=0.15em,
  bottomtitle=0.1em,
  boxrule=0.1em,
  minted language=#2,
  top=1mm,
  bottom=1mm,
  minted options={%
      tabsize=4,
      breaklines,
      xleftmargin=-0.75em,
      fontsize=\footnotesize,
      highlightcolor=gray!30,
      ignorelexererrors,
      #4
    },
  coltitle=black,
  colbacktitle=gray!20!white,
  title={#3},
  list entry={\protect\numberline{\thetcbcounter}#3},
  #1
}

\NewTotalTCBox{\cde}{mv}{
  on line,
  boxsep=0pt,
  left=1.5pt,
  right=1.5pt,
  top=1pt,
  bottom=1pt,
  colframe=gray!20,
  colback=gray!20,
  minted options={%
      ignorelexererrors
    },
  rounded corners,
  boxrule=0pt,
}{\mintinline{#1}{#2}}

\newtcolorbox{goodbox}[1][]{
  colback=green!20,
  colframe=green!50!black,
  boxrule=0.5pt,
  arc=4mm,
  auto outer arc,
  #1
}

\newtcolorbox{badbox}[1][]{
  colback=red!20,
  colframe=red!50!black,
  boxrule=0.5pt,
  arc=4mm,
  auto outer arc,
  #1
}

\newtcolorbox{commentbox}[1][]{
  colback=gray!20,
  colframe=gray!50!black,
  boxrule=0.5pt,
  arc=4mm,
  auto outer arc,
  #1
}

%
% Tweaks
%

% Allow hyphenation after a hyphen
\providecommand{\allowhyphens}{\ifvmode\else\nobreak\hspace{0pt}\fi}

% Redefine bullet list character to a dash (demi-cadratin)
\setlist[itemize,1]{label=--}

% To number paragraphs and subparagraphs
\setcounter{secnumdepth}{5}

% Paragraph indentation
% \setlength{\parindent}{0pt}
% \setlength\parskip{\medskipamount}

% Avoid orphans at the end of a page, encourage page breaks if there are
% a section with less than 3 lines
% https://tex.stackexchange.com/a/723704/85416
\makeatletter
\patchcmd\@afterheading{\clubpenalty \@M}{\clubpenalties 3 \@M\@M 5000 }{%
  \typeout{patched}}{\typeout{patch failed}
}
\makeatother

% Allow for short text below parts
% https://tex.stackexchange.com/a/336401/85416
% \makeatletter
% \newcommand{\extraPartText}[1]{\def\@extraPartText{#1}}
% \pretocmd{\@endpart}{\vspace{8ex}\begingroup\centering\@extraPartText\par\endgroup\let\@extraPartText\relax}{}{}
% \makeatother

% Description item and text are displayed by default on the same line
% this is not very readable. This command changes the style to display
% the description text on the next line.
% https://tex.stackexchange.com/a/430454/85416
% https://tex.stackexchange.com/a/726879/85416
\AddToHook{cmd/descriptionlabel/after}{\rule[-8pt]{0pt}{0pt}}
\setlist[description]{
  style=nextline,
  labelindent=0pt,
  leftmargin=1cm,
  itemindent=\dimexpr-5pt-\labelsep\relax
}

% Workaround for mintedinline in item
% https://tex.stackexchange.com/a/723530/85416
\NewDocumentCommand{\minteditem}{mv}{%
  \item[\mintinline{#1}{#2}]%
}

% Highlight text in yellow
\newtcbox{\hl}{on line, boxrule=0.5pt, colframe=black, colback=yellow!30, sharp corners, boxsep=0pt, left=2pt, right=2pt, top=2pt, bottom=2pt}

% For exercises and solutions
\newcommand\correctchoice{\stackinset{c}{}{c}{}{$\times$}{$\bigcirc$}}
\newcommand\choice{$\bigcirc$}
