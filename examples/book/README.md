# Einstein Article

I was looking for a long article to give as an example for TexSmith, and the Wikipedia article on Albert Einstein seemed like a good candidate.
I took the article's wikitext and converted it to markdown using a series of Perl one-liners to clean up the wikitext syntax.

The rest was done by hand, cleaning up some remaining issues and adding LaTeX syntax where needed.

```bash
perl -pi -e 's/–/-/gm' article.md
perl -pi -e 's/– / -- /gm' article.md
perl -pi -e "s/''/\"/gm" article.md
perl -pi -e 's/\{\{See also.*?\}\}//gm' article.md
perl -pi -e 's/\{\{spaces\}\}//gm' article.md

perl -pi -e 's/^\[\[Category:.*?\]\]$//gm' article.md
perl -pi -e 's/^=====\s*(.*?)\s*=====$/#### \1/gm' article.md
perl -pi -e 's/^====\s*(.*?)\s*====$/### \1/gm' article.md
perl -pi -e 's/^===\s*(.*?)\s*===$/## \1/gm' article.md
perl -pi -e 's/^==\s*(.*?)\s*==$/# \1/gm' article.md

perl -Mutf8 -CS -pi -e 's/\{\{Sfnp\b(?:(?>[^{}]+)|(?0))*\}\}//g' article.md
perl -pi -e 's/<!--.*?-->//gm' article.md

perl -CS -Mutf8 -pi -e 's/\[\[(?!File)([^\]\|]+)\]\]/$1/gm' article.md
perl -CS -Mutf8 -pi -e 's/\[\[(?!File).*?(?>\|)([^\]]+)\]\]/$1/gm' article.md

perl -pi -e 's/<ref name="([a-zA-Z0-9]{5})"\/>/^[\1]/gm' article.md
perl -pi -e 's/<ref>.*?doi=([^\s]+).*?<\/ref>/^[\1]/gm' article.md
perl -pi -e 's/<ref>\{\{cite web.*?\}\}<\/ref>//gm' article.md
perl -pi -e 's/<ref name=[^\]]+>.*?doi=([^\s]+).*?<\/ref>/^[\1]/gm' article.md

perl -pi -e 's/\[\[File:.*?\]\]//gm' article.md
perl -pi -e 's/<ref>.*?<\/ref>//gm' article.md
perl -pi -e 's/<ref name=[^\]]+\/>//gm' article.md
perl -pi -e 's/<ref name=[^>]+>.*?<\/ref>//gm' article.md

perl -Mutf8 -CS -pi -e 's/\{\{\b(?:(?>[^{}]+)|(?0))*\}\}//g' article.md
```

## Disclaimer

This is not an official Wikipedia publication, this is not the full article, and it may contain errors.
