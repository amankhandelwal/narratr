"""On-click reveals, as PowerPoint timing XML.

python-pptx has no animation API, so this writes `p:timing` directly. The shape
is the one verified to survive Google Slides' import (see the design spec): a
main sequence of click groups, each holding Fade entrance effects -- the first
On click, the rest With previous.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import count
from typing import Any

from lxml import etree
from pptx.oxml.ns import qn

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
FADE_MS = 500


def _fade(ids: Iterator[int], spid: int, node_type: str) -> str:
	target = f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
	return (
		f'<p:par><p:cTn id="{next(ids)}" presetID="10" presetClass="entr" presetSubtype="0" '
		f'fill="hold" nodeType="{node_type}"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
		"<p:childTnLst>"
		f'<p:set><p:cBhvr><p:cTn id="{next(ids)}" dur="1" fill="hold"><p:stCondLst>'
		f'<p:cond delay="0"/></p:stCondLst></p:cTn>{target}<p:attrNameLst>'
		"<p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
		'<p:to><p:strVal val="visible"/></p:to></p:set>'
		f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{next(ids)}" '
		f'dur="{FADE_MS}"/>{target}</p:cBhvr></p:animEffect>'
		"</p:childTnLst></p:cTn></p:par>"
	)


def timing_xml(groups: list[list[int]]) -> str:
	ids = count(3)  # 1 and 2 are the root and the main sequence
	clicks = ""
	for group in groups:
		effects = "".join(
			_fade(ids, spid, "clickEffect" if i == 0 else "withEffect")
			for i, spid in enumerate(group)
		)
		clicks += (
			f'<p:par><p:cTn id="{next(ids)}" fill="hold"><p:stCondLst>'
			'<p:cond delay="indefinite"/></p:stCondLst><p:childTnLst>'
			f'<p:par><p:cTn id="{next(ids)}" fill="hold"><p:stCondLst><p:cond delay="0"/>'
			f"</p:stCondLst><p:childTnLst>{effects}</p:childTnLst></p:cTn></p:par>"
			"</p:childTnLst></p:cTn></p:par>"
		)
	return (
		f'<p:timing xmlns:p="{P}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" '
		'restart="never" nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" '
		'nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
		f"{clicks}</p:childTnLst></p:cTn>"
		'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl>'
		"</p:cond></p:prevCondLst>"
		'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl>'
		"</p:cond></p:nextCondLst>"
		"</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"
	)


def apply(slide: Any, groups: list[list[int]]) -> None:
	groups = [g for g in groups if g]
	if not groups:
		return
	element = slide._element
	timing = etree.fromstring(timing_xml(groups))
	# Schema order: cSld, clrMapOvr, transition, timing, extLst.
	ext = element.find(qn("p:extLst"))
	if ext is not None:
		ext.addprevious(timing)
	else:
		element.append(timing)


def click_groups(element: Any) -> list[list[int]]:
	"""Read the click groups back out of a slide's XML: one shape id per effect."""
	seq = element.find(f".//{qn('p:cTn')}[@nodeType='mainSeq']")
	if seq is None:
		return []
	groups: list[list[int]] = []
	for click in seq.find(qn("p:childTnLst")):
		effects = [e for e in click.iter(qn("p:cTn")) if e.get("presetClass") == "entr"]
		groups.append([int(e.find(f".//{qn('p:spTgt')}").get("spid")) for e in effects])
	return groups
