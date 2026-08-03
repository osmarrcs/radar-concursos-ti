from __future__ import annotations
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

TRACKING={"utm_source","utm_medium","utm_campaign","utm_content","utm_term","fbclid","gclid"}

def normalize_url(url: str) -> str:
    parts=urlsplit(url.strip())
    query=urlencode([(k,v) for k,v in parse_qsl(parts.query,keep_blank_values=True) if k.lower() not in TRACKING])
    path=parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(),parts.netloc.lower(),path,query,""))

class LinkParser(HTMLParser):
    def __init__(self,base_url: str):
        super().__init__(); self.base_url=base_url; self.items=[]; self.href=None; self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a": self.href=dict(attrs).get("href"); self.text=[]
    def handle_data(self,data):
        if self.href is not None: self.text.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.href is not None:
            title=" ".join("".join(self.text).split())
            absolute=urljoin(self.base_url,self.href)
            if absolute.startswith(("http://","https://")): self.items.append({"title":title or absolute,"url":normalize_url(absolute)})
            self.href=None; self.text=[]

def parse_html(content: str, base_url: str) -> list[dict[str,str]]:
    parser=LinkParser(base_url); parser.feed(content); return parser.items

def parse_feed(content: str, base_url: str) -> list[dict[str,str]]:
    root=ET.fromstring(content)
    items=[]
    for node in root.iter():
        tag=node.tag.rsplit("}",1)[-1].lower()
        if tag not in {"item","entry"}: continue
        title=""; link=""
        for child in node:
            ctag=child.tag.rsplit("}",1)[-1].lower()
            if ctag=="title" and child.text: title=child.text.strip()
            elif ctag=="link": link=child.attrib.get("href") or (child.text or "").strip()
        if link: items.append({"title":title or link,"url":normalize_url(urljoin(base_url,link))})
    return items

def deduplicate(items: list[dict[str,str]]) -> list[dict[str,str]]:
    unique={}
    for item in items: unique.setdefault(normalize_url(item["url"]),{"title":item.get("title") or item["url"],"url":normalize_url(item["url"])})
    return list(unique.values())
