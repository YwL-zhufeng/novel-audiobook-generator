#!/usr/bin/env python3
"""
Gradio Web UI for Novel Audiobook Generator
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

import gradio as gr

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.generator import AudiobookGenerator
from src.config import Config, TTSConfig, TextConfig, OutputConfig
from src.text_processor import TextProcessor
from src.dialogue_detector import DialogueDetector


# Global state for session
@dataclass
class SessionState:
    """Session state management."""
    generator: Optional[AudiobookGenerator] = None
    config: Optional[Config] = None
    cloned_voices: Dict[str, str] = None
    uploaded_file: Optional[str] = None
    text_preview: Optional[str] = None
    detected_characters: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.cloned_voices is None:
            self.cloned_voices = {}


# Initialize session state
session = SessionState()


def extract_text_preview(file_path: str, max_chars: int = 2000) -> str:
    """Extract text preview from uploaded file."""
    try:
        processor = TextProcessor()
        text = processor.extract_text(file_path)
        return text[:max_chars] + "..." if len(text) > max_chars else text
    except Exception as e:
        return f"Error extracting text: {str(e)}"


def detect_characters_from_text(file_path: str) -> List[Dict[str, Any]]:
    """Detect characters in the text."""
    try:
        processor = TextProcessor()
        detector = DialogueDetector()
        
        text = processor.extract_text(file_path)
        segments = detector.detect_dialogue(text[:50000])  # Limit for speed
        characters = detector.extract_characters(segments)
        
        # Sort by dialogue count
        sorted_chars = sorted(characters.items(), key=lambda x: x[1], reverse=True)
        return [{"name": name, "dialogues": count} for name, count in sorted_chars[:20]]
    except Exception as e:
        return []


def initialize_generator(
    backend: str,
    api_key: str,
    max_workers: int,
    chunk_size: int,
    detect_dialogue: bool
) -> str:
    """Initialize the audiobook generator."""
    global session
    
    try:
        config = Config(
            tts=TTSConfig(
                backend=backend,
                api_key=api_key if api_key else None,
                max_workers=max_workers
            ),
            text=TextConfig(
                chunk_size=chunk_size,
                detect_dialogue=detect_dialogue
            )
        )
        
        session.config = config
        session.generator = AudiobookGenerator(
            tts_backend=backend,
            api_key=api_key if api_key else None,
            max_workers=max_workers,
            config=config
        )
        
        return f"✅ Generator initialized with {backend} backend"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def clone_voice_ui(
    voice_name: str,
    audio_file: str,
    description: str
) -> str:
    """Clone a voice from audio sample."""
    global session
    
    if not session.generator:
        return "❌ Please initialize generator first"
    
    if not audio_file:
        return "❌ Please upload an audio sample"
    
    try:
        voice_id = session.generator.clone_voice(
            voice_name=voice_name,
            sample_audio_path=audio_file,
            description=description if description else None
        )
        session.cloned_voices[voice_name] = voice_id
        return f"✅ Voice '{voice_name}' cloned successfully"
    except Exception as e:
        return f"❌ Error cloning voice: {str(e)}"


def generate_preview_ui(
    preview_text: str,
    voice: str,
    preview_length: int,
    use_character_voices: bool
) -> tuple:
    """Generate preview audio."""
    global session
    
    if not session.generator:
        return None, "❌ Please initialize generator first"
    
    if not preview_text:
        return None, "❌ No preview text available"
    
    try:
        if use_character_voices and session.detected_characters:
            # Build character voice mapping from cloned voices
            char_voices = {}
            for char in session.detected_characters[:5]:  # Top 5 characters
                if session.cloned_voices:
                    # Assign cloned voices to characters
                    voice_list = list(session.cloned_voices.keys())
                    if voice_list:
                        char_voices[char] = voice_list[min(len(voice_list)-1, session.detected_characters.index(char))]
            
            audio_path, info = session.generator.preview_with_characters(
                text=preview_text,
                narrator_voice=voice,
                character_voices=char_voices if char_voices else None,
                preview_length=preview_length
            )
            return audio_path, f"✅ Preview generated with characters\n\n{info}"
        else:
            audio_path = session.generator.generate_preview(
                text=preview_text,
                voice=voice,
                preview_length=preview_length
            )
            preview_snippet = preview_text[:200].replace('\n', ' ')
            return audio_path, f"✅ Preview generated\n\nPreview text:\n{preview_snippet}..."
    except Exception as e:
        return None, f"❌ Error: {str(e)}"


def generate_audiobook_ui(
    file: str,
    voice: str,
    use_character_voices: bool,
    title: str,
    artist: str,
    album: str,
    cover_image: str,
    progress=gr.Progress()
) -> tuple:
    """Generate audiobook with progress tracking and metadata."""
    global session
    
    if not session.generator:
        return None, "❌ Please initialize generator first"
    
    if not file:
        return None, "❌ Please upload a file"
    
    try:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        output_path = output_dir / f"{Path(file).stem}_audiobook.mp3"
        
        # Build metadata
        metadata = {}
        if title:
            metadata['title'] = title
        if artist:
            metadata['artist'] = artist
            metadata['composer'] = artist
        if album:
            metadata['album'] = album
        if cover_image:
            metadata['cover_image'] = cover_image
        
        # Progress callback
        def progress_callback(p: float):
            progress(p, desc=f"Generating... {int(p*100)}%")
        
        if use_character_voices and session.detected_characters:
            # Use character voice mode
            result_path = session.generator.generate_with_characters(
                input_path=file,
                narrator_voice=voice,
                output_path=str(output_path)
            )
            # Add metadata after generation
            if metadata:
                session.generator.audio_utils.add_metadata(result_path, metadata)
        else:
            # Standard mode with metadata
            result_path = session.generator.generate_audiobook(
                input_path=file,
                output_path=str(output_path),
                voice=voice,
                progress_callback=progress_callback,
                metadata=metadata if metadata else None
            )
        
        return result_path, f"✅ Audiobook generated: {Path(result_path).name}"
    except Exception as e:
        return None, f"❌ Error: {str(e)}"


def handle_file_upload(file: str) -> tuple:
    """Handle file upload and extract preview."""
    global session
    
    if not file:
        return "", [], "No file uploaded", ""
    
    session.uploaded_file = file
    
    # Extract preview
    preview = extract_text_preview(file, max_chars=1500)
    session.text_preview = preview
    
    # Detect characters
    characters = detect_characters_from_text(file)
    session.detected_characters = [c["name"] for c in characters]
    
    status = f"📄 {Path(file).name} uploaded. Detected {len(characters)} characters."
    
    # Extract preview text for preview tab (first 1000 chars)
    preview_text = extract_text_preview(file, max_chars=1000)
    
    return preview, characters, status, preview_text


# ===== Gradio UI =====

def create_ui() -> gr.Blocks:
    """Create the Gradio UI."""
    
    with gr.Blocks(
        title="Novel Audiobook Generator",
        theme=gr.themes.Soft(),
        css="""
        .container { max-width: 1200px; margin: 0 auto; }
        .preview-box { max-height: 300px; overflow-y: auto; }
        .voice-card { border: 1px solid #ddd; padding: 10px; border-radius: 8px; margin: 5px 0; }
        """
    ) as demo:
        
        gr.Markdown("""
        # 📚 Novel Audiobook Generator
        
        Transform your novels into audiobooks with AI-powered text-to-speech and voice cloning.
        """)
        
        with gr.Tabs():
            
            # ===== Tab 1: Quick Start =====
            with gr.TabItem("🚀 Quick Start"):
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 1. Configure TTS Backend")
                        
                        backend_dropdown = gr.Dropdown(
                            choices=["elevenlabs", "xtts", "kokoro"],
                            value="elevenlabs",
                            label="TTS Backend"
                        )
                        
                        api_key_input = gr.Textbox(
                            label="API Key (for ElevenLabs)",
                            placeholder="sk-...",
                            type="password",
                            visible=True
                        )
                        
                        def toggle_api_key(backend):
                            return gr.update(visible=(backend == "elevenlabs"))
                        
                        backend_dropdown.change(
                            fn=toggle_api_key,
                            inputs=backend_dropdown,
                            outputs=api_key_input
                        )
                        
                        max_workers_slider = gr.Slider(
                            minimum=1, maximum=10, value=4, step=1,
                            label="Concurrent Workers"
                        )
                        
                        init_btn = gr.Button("Initialize Generator", variant="primary")
                        init_status = gr.Textbox(label="Status", interactive=False)
                        
                        init_btn.click(
                            fn=initialize_generator,
                            inputs=[backend_dropdown, api_key_input, max_workers_slider,
                                   gr.State(4000), gr.State(True)],
                            outputs=init_status
                        )
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### 2. Upload Novel")
                        
                        file_input = gr.File(
                            label="Upload Novel (TXT, EPUB, PDF)",
                            file_types=[".txt", ".epub", ".pdf"]
                        )
                        
                        with gr.Row():
                            preview_box = gr.Textbox(
                                label="Text Preview",
                                lines=10,
                                interactive=False,
                                elem_classes=["preview-box"]
                            )
                            
                            character_table = gr.Dataframe(
                                headers=["Character", "Dialogues"],
                                label="Detected Characters",
                                interactive=False
                            )
                        
                        upload_status = gr.Textbox(label="Upload Status", interactive=False)
                        
                        # Hidden state for preview text
                        preview_text_state = gr.State("")
                        
                        file_input.change(
                            fn=handle_file_upload,
                            inputs=file_input,
                            outputs=[preview_box, character_table, upload_status, preview_text_state]
                        )
                
                gr.Markdown("---")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 3. Metadata (Optional)")
                        
                        title_input = gr.Textbox(
                            label="Book Title",
                            placeholder="Enter book title..."
                        )
                        
                        artist_input = gr.Textbox(
                            label="Author / Narrator",
                            placeholder="Enter author or narrator name..."
                        )
                        
                        album_input = gr.Textbox(
                            label="Series / Album",
                            placeholder="Enter series name (optional)..."
                        )
                        
                        cover_input = gr.Image(
                            label="Cover Image (Optional)",
                            type="filepath"
                        )
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### 4. Generate Audiobook")
                        
                        voice_input = gr.Textbox(
                            label="Voice to Use",
                            value="default",
                            placeholder="Voice name or 'default'"
                        )
                        
                        use_characters_checkbox = gr.Checkbox(
                            label="Use Character Voices (if detected)",
                            value=False
                        )
                        
                        generate_btn = gr.Button("🎙️ Generate Audiobook", variant="primary", size="lg")
                        
                        output_audio = gr.Audio(label="Generated Audiobook", type="filepath")
                        generate_status = gr.Textbox(label="Generation Status")
                        
                        generate_btn.click(
                            fn=generate_audiobook_ui,
                            inputs=[file_input, voice_input, use_characters_checkbox,
                                   title_input, artist_input, album_input, cover_input],
                            outputs=[output_audio, generate_status]
                        )
            
            
            # ===== Tab 2: Real-time Preview =====
            with gr.TabItem("👂 Preview"):
                
                gr.Markdown("""
                ### 🎧 Real-time Preview
                
                Generate a short preview before processing the entire book. This helps you verify voice quality and character attribution.
                """)
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Preview Settings")
                        
                        preview_voice_input = gr.Textbox(
                            label="Voice to Use",
                            value="default",
                            placeholder="Voice name or 'default'"
                        )
                        
                        preview_length_slider = gr.Slider(
                            minimum=100, maximum=1000, value=300, step=50,
                            label="Preview Length (characters)"
                        )
                        
                        preview_use_chars = gr.Checkbox(
                            label="Use Character Voices",
                            value=True,
                            info="Enable if you want to preview character voice attribution"
                        )
                        
                        preview_btn = gr.Button("🔊 Generate Preview", variant="primary")
                        
                        preview_status = gr.Textbox(
                            label="Preview Info",
                            lines=5,
                            interactive=False
                        )
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### Preview Text")
                        
                        preview_text_input = gr.Textbox(
                            label="Edit preview text (or use auto-loaded from file)",
                            lines=8,
                            placeholder="Upload a file to auto-load preview text, or paste text here..."
                        )
                        
                        preview_audio = gr.Audio(
                            label="Preview Audio",
                            type="filepath",
                            autoplay=False
                        )
                
                # Link file upload to preview text
                file_input.change(
                    fn=lambda x: x,
                    inputs=preview_text_state,
                    outputs=preview_text_input
                )
                
                preview_btn.click(
                    fn=generate_preview_ui,
                    inputs=[preview_text_input, preview_voice_input, preview_length_slider, preview_use_chars],
                    outputs=[preview_audio, preview_status]
                )
            
            
            # ===== Tab 3: Voice Cloning =====
            with gr.TabItem("🎭 Voice Cloning"):
                
                gr.Markdown("""
                ### Clone Custom Voices
                
                Upload 10-20 seconds of clear speech to create a custom voice.
                You can then use the voice name in generation.
                """)
                
                with gr.Row():
                    with gr.Column():
                        voice_name_input = gr.Textbox(
                            label="Voice Name",
                            placeholder="e.g., narrator, hero, heroine"
                        )
                        
                        voice_audio_input = gr.Audio(
                            label="Voice Sample (10-20 seconds)",
                            type="filepath"
                        )
                        
                        voice_desc_input = gr.Textbox(
                            label="Description (optional)",
                            placeholder="e.g., A warm, mature male voice"
                        )
                        
                        clone_btn = gr.Button("Clone Voice", variant="primary")
                        clone_status = gr.Textbox(label="Status")
                        
                        clone_btn.click(
                            fn=clone_voice_ui,
                            inputs=[voice_name_input, voice_audio_input, voice_desc_input],
                            outputs=clone_status
                        )
                    
                    with gr.Column():
                        gr.Markdown("### Cloned Voices")
                        cloned_voices_list = gr.JSON(label="Voice Registry", value={})
                        
                        def refresh_voices():
                            return session.cloned_voices
                        
                        refresh_btn = gr.Button("Refresh List")
                        refresh_btn.click(fn=refresh_voices, outputs=cloned_voices_list)
            
            
            # ===== Tab 4: Advanced Settings =====
            with gr.TabItem("⚙️ Advanced"):
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Text Processing")
                        
                        chunk_size_slider = gr.Slider(
                            minimum=1000, maximum=10000, value=4000, step=500,
                            label="Chunk Size (characters)"
                        )
                        
                        detect_dialogue_checkbox = gr.Checkbox(
                            label="Detect Dialogue",
                            value=True
                        )
                        
                        language_dropdown = gr.Dropdown(
                            choices=["auto", "chinese", "english"],
                            value="auto",
                            label="Language"
                        )
                    
                    with gr.Column():
                        gr.Markdown("### Output Settings")
                        
                        format_dropdown = gr.Dropdown(
                            choices=["mp3", "wav", "m4a"],
                            value="mp3",
                            label="Output Format"
                        )
                        
                        bitrate_dropdown = gr.Dropdown(
                            choices=["128k", "192k", "256k", "320k"],
                            value="192k",
                            label="Bitrate"
                        )
                        
                        normalize_checkbox = gr.Checkbox(
                            label="Normalize Volume",
                            value=True
                        )
                        
                        split_chapters_checkbox = gr.Checkbox(
                            label="Split by Chapters",
                            value=False
                        )
                
                gr.Markdown("---")
                
                gr.Markdown("""
                ### 💡 Tips
                
                - **Chunk Size**: Smaller chunks = more frequent progress updates, but slightly slower overall
                - **Concurrent Workers**: More workers = faster generation, but watch API rate limits
                - **Voice Cloning**: Use 10-20 seconds of clear, noise-free speech for best results
                - **Character Voices**: Enable dialogue detection to automatically assign voices to characters
                - **Preview Mode**: Always use Preview first to verify voice quality before generating the full audiobook
                """)
        
        
        gr.Markdown("---")
        gr.Markdown("""
        <div style="text-align: center; color: #666;">
            Novel Audiobook Generator v1.2.2 | 
            <a href="https://github.com/YwL-zhufeng/novel-audiobook-generator">GitHub</a>
        </div>
        """)
    
    return demo


def main():
    """Launch the web UI."""
    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main()
