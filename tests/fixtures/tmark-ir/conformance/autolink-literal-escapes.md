# Text that GFM would turn into a link

The GFM autolink-literal extension is on: `http://`, `https://`,
`mailto:`, `xmpp:`, `www.` at a word start and `user@host.tld` become
links. Literal text escapes the character that fires (printer critic U10);
a `www.` link whose text is its address prints bare.

## input

```md
see http\://x.y, www\.x.y/z, me\@x.y and www.example.com or ftp://x.y
```

## canonical

```md
see http\://x.y, www\.x.y/z, me\@x.y and www.example.com or ftp://x.y
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "see http://x.y, www.x.y/z, me@x.y and "
        },
        {
          "type": "Link",
          "content": [
            {
              "type": "Str",
              "text": "www.example.com"
            }
          ],
          "target": {
            "type": "Url",
            "value": "http://www.example.com"
          }
        },
        {
          "type": "Str",
          "text": " or ftp://x.y"
        }
      ]
    }
  ]
}
```
