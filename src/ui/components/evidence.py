import streamlit as st

from src.core.models import ChatMessage, Match
from src.services.curation import CuratedContext
from src.ui.components.primitives import esc, icon, section_title
from src.ui.components.source_formatting import display_title, present_source, readable_body


def render_source_text(text: str, title: str, kind: str, *, citation: int | None = None,
                       chunk: int = 0, source_text: str | None = None) -> None:
    """Show source metadata separately from evidence; never generate a new summary."""
    parsed = present_source(text)
    metadata = present_source(source_text if source_text is not None else text).metadata
    publisher = metadata.get("SOURCE", "Supplied document")
    date = metadata.get("DATE", "")
    with st.container(border=True):
        reference = f'<span class="evidence-reference">[{citation}]</span>' if citation else icon("file", 22)
        st.html(f'<div class="evidence-heading">{reference}<div><h4>{esc(display_title(title))}</h4>'
                f'<p>{esc(publisher)}</p></div></div>'
                f'<div class="evidence-meta"><span>{esc(kind)}</span>'
                + (f'<span>Source date · {esc(date)}</span>' if date else '')
                + (f'<span>Passage {chunk}</span>' if chunk else '') + '</div>')
        st.markdown(readable_body(parsed.body))
        with st.popover("View original text", icon=":material/article:"):
            st.caption("Exact retrieved passage" if citation else "Original supplied document")
            st.code(text, language=None, wrap_lines=True)


def render_evidence(match: Match, context: CuratedContext, latest: ChatMessage | None) -> None:
    manifest = context.manifest
    with st.container(key="insights-panel", gap="small"):
        st.html(section_title("Match insights", "file"))
        overview, sources = st.tabs(["Overview", f"Sources ({len(manifest.sources)})"])
        with overview:
            if manifest.metrics:
                st.html('<div class="metrics">' + ''.join(
                    f'<div class="metric"><span>{esc(m.label)}</span><strong>{esc(m.value)}</strong></div>'
                    for m in manifest.metrics[:3]) + '</div>')
                subject = match.participants[0] if match.participants else match.title
                st.caption(subject + (" · Fictional sample figures" if match.sample else " · Curated figures"))
            for insight in manifest.insights:
                source = next(s for s in manifest.sources if s.id == insight.source_id)
                st.html(f'<div class="insight">{icon("clock",24)}<div><strong>{esc(insight.title)}</strong><p>{esc(insight.text)}</p><p>Source: {esc(source.title)}</p></div></div>')
            # Current answer citation numbers belong to that answer, not a global source list.
            evidence = latest.evidence if latest else []
            names = {f.name: s for s, f in zip(manifest.sources, context.files, strict=True)}
            st.html('<div class="source-list-label">' + ("Sources behind this answer" if evidence else "Available match context") + '</div>')
            if evidence:
                for i, passage in enumerate(evidence, 1):
                    spec = names.get(passage.source)
                    title = display_title(spec.title if spec else passage.source)
                    description = (spec.summary or spec.kind) if spec else f"Passage {passage.chunk}"
                    st.html(f'<div class="source-row">{icon("file")}<div><strong><b>[{i}]</b>{esc(title)}</strong><p>{esc(description)}</p></div></div>')
            else:
                for source in manifest.sources:
                    st.html(f'<div class="source-row">{icon("file")}<div><strong>{esc(display_title(source.title))}</strong><p>{esc(source.summary or source.kind)}</p></div></div>')
            if manifest.missing_information:
                st.html(f'<div class="missing">{icon("info",15)}<span>{esc(manifest.missing_information)}</span></div>')
        with sources:
            if not manifest.sources:
                st.caption("Source material is not available for this match yet.")
            for source, file in zip(manifest.sources, context.files, strict=True):
                with st.expander(display_title(source.title), icon=":material/description:"):
                    render_source_text(file.content.decode("utf-8-sig"), source.title,
                                       source.kind + (" · Fictional sample" if match.sample else ""))
                    if source.url:
                        st.link_button("Original source", source.url)


def render_passages(message: ChatMessage, context: CuratedContext) -> None:
    sources = {f.name: (s, f) for s, f in zip(context.manifest.sources, context.files, strict=True)}
    with st.expander("Explore the supporting evidence", icon=":material/manage_search:"):
        st.caption("Passages used for this answer. Reference numbers match the citations in the conversation.")
        for i, passage in enumerate(message.evidence, 1):
            spec, file = sources.get(passage.source, (None, None))
            render_source_text(passage.text, spec.title if spec else passage.source,
                               spec.kind if spec else "Retrieved evidence", citation=i,
                               chunk=passage.chunk,
                               source_text=file.content.decode("utf-8-sig") if file else None)
