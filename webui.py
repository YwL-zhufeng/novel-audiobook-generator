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
from src.tts_backends.doubao import DoubaoBackend, ModelType


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
    doubao_backend: Optional[DoubaoBackend] = None
    
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
    app_id: str,
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
        
        # Initialize Doubao backend separately if needed
        if backend == "doubao":
            session.doubao_backend = DoubaoBackend(
                app_id=app_id if app_id else None,
                access_token=api_key if api_key else None
            )
        
        session.generator = AudiobookGenerator(
            tts_backend=backend,
            api_key=api_key if api_key else None,
            app_id=app_id if app_id else None,
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


def batch_generate_ui(
    files: List[str],
    voice: str,
    use_character_voices: bool,
    progress=gr.Progress()
) -> tuple:
    """Batch generate audiobooks from multiple files."""
    global session
    
    if not session.generator:
        return None, "❌ Please initialize generator first"
    
    if not files or len(files) == 0:
        return None, "❌ Please upload at least one file"
    
    try:
        total_files = len(files)
        
        def batch_progress(current: int, total: int, file_progress: float):
            overall = (current + file_progress) / total
            progress(overall, desc=f"Processing {current+1}/{total}...")
        
        results = session.generator.batch_generate(
            input_files=files,
            voice=voice,
            use_character_voices=use_character_voices,
            progress_callback=batch_progress
        )
        
        # Build results table
        output_data = []
        completed = 0
        failed = 0
        
        for r in results:
            status_icon = "✅" if r['status'] == 'completed' else "❌"
            output_name = Path(r['output']).name if r['output'] else "N/A"
            output_data.append([
                Path(r['input']).name,
                status_icon,
                output_name,
                r['error'] if r['error'] else ""
            ])
            if r['status'] == 'completed':
                completed += 1
            else:
                failed += 1
        
        summary = f"Batch complete: {completed} succeeded, {failed} failed"
        return output_data, summary
        
    except Exception as e:
        return None, f"❌ Batch error: {str(e)}"


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
                            choices=["elevenlabs", "xtts", "kokoro", "doubao"],
                            value="doubao",
                            label="TTS Backend"
                        )
                        
                        api_key_input = gr.Textbox(
                            label="API Key / Access Token",
                            placeholder="Enter API key or access token...",
                            type="password",
                            visible=True
                        )
                        
                        app_id_input = gr.Textbox(
                            label="App ID (for Doubao)",
                            placeholder="Enter Doubao App ID (optional)...",
                            visible=True
                        )
                        
                        def toggle_api_key(backend):
                            return gr.update(visible=(backend in ["elevenlabs", "doubao"]))
                        
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
                            inputs=[backend_dropdown, api_key_input, app_id_input, max_workers_slider,
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
                ### 🎭 Voice Cloning with Doubao
                
                Clone any voice with just **5 seconds** of audio. Supports multiple cloning models:
                - **ICL 2.0** (Recommended): Best quality, fastest training
                - **ICL 1.0**: Standard voice cloning
                - **DiT Standard**: Focus on timbre
                - **DiT Restoration**: Timbre + speaking style
                """)
                
                with gr.Tabs():
                    # Sub-tab 1: Clone New Voice
                    with gr.TabItem("➕ Clone New Voice"):
                        with gr.Row():
                            with gr.Column():
                                gr.Markdown("### Voice Information")
                                
                                clone_speaker_id = gr.Textbox(
                                    label="Speaker ID",
                                    placeholder="e.g., S_narrator, S_hero (must start with S_)",
                                    value="S_my_voice"
                                )
                                
                                clone_model_type = gr.Dropdown(
                                    choices=[
                                        ("ICL 2.0 (Recommended)", "icl2"),
                                        ("ICL 1.0", "icl1"),
                                        ("DiT Standard", "dit_standard"),
                                        ("DiT Restoration", "dit_restoration")
                                    ],
                                    value="icl2",
                                    label="Cloning Model"
                                )
                                
                                clone_language = gr.Dropdown(
                                    choices=[
                                        ("Chinese", 0),
                                        ("English", 1),
                                        ("Japanese", 2),
                                        ("Spanish", 3)
                                    ],
                                    value=0,
                                    label="Language"
                                )
                                
                                clone_wait_completion = gr.Checkbox(
                                    label="Wait for Training Completion",
                                    value=True,
                                    info="Wait for voice training to complete (may take 10-30 seconds)"
                                )
                            
                            with gr.Column():
                                gr.Markdown("### Audio Sample")
                                
                                clone_audio_input = gr.Audio(
                                    label="Upload Voice Sample (5-20 seconds)",
                                    type="filepath"
                                )
                                
                                clone_status_output = gr.Textbox(
                                    label="Training Status",
                                    lines=5,
                                    interactive=False
                                )
                                
                                clone_btn = gr.Button("🎙️ Start Cloning", variant="primary", size="lg")
                                
                                def do_clone_voice(speaker_id, model_type, language, wait_completion, audio_file):
                                    global session
                                    
                                    if not session.doubao_backend:
                                        return "❌ Please initialize Doubao backend first (in Quick Start tab)"
                                    
                                    if not audio_file:
                                        return "❌ Please upload an audio sample"
                                    
                                    try:
                                        # Map UI values to ModelType
                                        model_map = {
                                            "icl1": ModelType.ICL_1_0,
                                            "icl2": ModelType.ICL_2_0,
                                            "dit_standard": ModelType.DIT_STANDARD,
                                            "dit_restoration": ModelType.DIT_RESTORATION
                                        }
                                        model = model_map.get(model_type, ModelType.ICL_2_0)
                                        
                                        # Start cloning
                                        cloned = session.doubao_backend.clone_voice(
                                            sample_audio_path=audio_file,
                                            speaker_id=speaker_id,
                                            model_type=model,
                                            language=language,
                                            wait_for_completion=wait_completion,
                                            timeout=120
                                        )
                                        
                                        status_text = f"✅ Voice cloning started!\n\n"
                                        status_text += f"Speaker ID: {cloned.speaker_id}\n"
                                        status_text += f"Status: {cloned.status_text}\n"
                                        status_text += f"Model: {model.name}\n"
                                        status_text += f"Training Count: {cloned.version}/10"
                                        
                                        if cloned.is_ready:
                                            status_text += "\n\n🎉 Voice is ready to use!"
                                            session.cloned_voices[speaker_id] = speaker_id
                                        else:
                                            status_text += "\n\n⏳ Training in progress..."
                                        
                                        return status_text
                                        
                                    except Exception as e:
                                        return f"❌ Error: {str(e)}"
                                
                                clone_btn.click(
                                    fn=do_clone_voice,
                                    inputs=[clone_speaker_id, clone_model_type, clone_language, clone_wait_completion, clone_audio_input],
                                    outputs=clone_status_output
                                )
                    
                    # Sub-tab 2: Manage Cloned Voices
                    with gr.TabItem("📋 Manage Voices"):
                        with gr.Row():
                            with gr.Column():
                                gr.Markdown("### Check Voice Status")
                                
                                check_speaker_id = gr.Textbox(
                                    label="Speaker ID",
                                    placeholder="Enter speaker ID to check..."
                                )
                                
                                check_btn = gr.Button("🔍 Check Status")
                                check_status_output = gr.Textbox(
                                    label="Voice Status",
                                    lines=6,
                                    interactive=False
                                )
                                
                                def check_voice_status(speaker_id):
                                    global session
                                    
                                    if not session.doubao_backend:
                                        return "❌ Please initialize Doubao backend first"
                                    
                                    if not speaker_id:
                                        return "❌ Please enter a speaker ID"
                                    
                                    try:
                                        voice = session.doubao_backend.get_voice_status(speaker_id)
                                        
                                        status_text = f"📊 Voice Status\n\n"
                                        status_text += f"Speaker ID: {voice.speaker_id}\n"
                                        status_text += f"Status: {voice.status_text}\n"
                                        status_text += f"Training Count: {voice.version}/10\n"
                                        status_text += f"Model Type: {voice.model_type}\n"
                                        
                                        if voice.create_time:
                                            status_text += f"Created: {voice.create_time}\n"
                                        
                                        if voice.is_ready:
                                            status_text += "\n✅ Ready to use!"
                                        elif voice.status == 1:
                                            status_text += "\n⏳ Still training..."
                                        elif voice.status == 3:
                                            status_text += "\n❌ Training failed"
                                        
                                        return status_text
                                        
                                    except Exception as e:
                                        return f"❌ Error: {str(e)}"
                                
                                check_btn.click(
                                    fn=check_voice_status,
                                    inputs=check_speaker_id,
                                    outputs=check_status_output
                                )
                            
                            with gr.Column():
                                gr.Markdown("### Activate Voice")
                                
                                activate_speaker_id = gr.Textbox(
                                    label="Speaker ID",
                                    placeholder="Enter speaker ID to activate..."
                                )
                                
                                gr.Markdown("""
                                ⚠️ **Warning**: Activating a voice will:
                                - Lock the voice for production use
                                - Prevent further training (even if under 10 times)
                                - Make the voice permanent
                                
                                Only activate when you're satisfied with the quality!
                                """)
                                
                                activate_btn = gr.Button("🔒 Activate Voice", variant="secondary")
                                activate_status = gr.Textbox(
                                    label="Activation Status",
                                    interactive=False
                                )
                                
                                def activate_voice(speaker_id):
                                    global session
                                    
                                    if not session.doubao_backend:
                                        return "❌ Please initialize Doubao backend first"
                                    
                                    if not speaker_id:
                                        return "❌ Please enter a speaker ID"
                                    
                                    try:
                                        success = session.doubao_backend.activate_voice(speaker_id)
                                        if success:
                                            return f"✅ Voice '{speaker_id}' activated successfully!\n\nThis voice is now locked and ready for production use."
                                        else:
                                            return f"❌ Failed to activate voice '{speaker_id}'"
                                    except Exception as e:
                                        return f"❌ Error: {str(e)}"
                                
                                activate_btn.click(
                                    fn=activate_voice,
                                    inputs=activate_speaker_id,
                                    outputs=activate_status
                                )
                    
                    # Sub-tab 3: Test Cloned Voice
                    with gr.TabItem("🧪 Test Voice"):
                        with gr.Row():
                            with gr.Column():
                                gr.Markdown("### Test Your Cloned Voice")
                                
                                test_speaker_id = gr.Textbox(
                                    label="Speaker ID",
                                    placeholder="Enter your cloned speaker ID..."
                                )
                                
                                test_text = gr.Textbox(
                                    label="Test Text",
                                    value="你好，这是克隆声音测试。Hello, this is a voice cloning test.",
                                    lines=3
                                )
                                
                                test_speed = gr.Slider(
                                    minimum=0.5, maximum=2.0, value=1.0, step=0.1,
                                    label="Speed"
                                )
                                
                                test_volume = gr.Slider(
                                    minimum=0.5, maximum=2.0, value=1.0, step=0.1,
                                    label="Volume"
                                )
                                
                                test_btn = gr.Button("🔊 Generate Test Audio", variant="primary")
                            
                            with gr.Column():
                                test_audio_output = gr.Audio(
                                    label="Test Audio",
                                    type="filepath",
                                    autoplay=False
                                )
                                
                                test_status = gr.Textbox(
                                    label="Status",
                                    interactive=False
                                )
                                
                                def test_cloned_voice(speaker_id, text, speed, volume):
                                    global session
                                    
                                    if not session.doubao_backend:
                                        return None, "❌ Please initialize Doubao backend first"
                                    
                                    if not speaker_id:
                                        return None, "❌ Please enter a speaker ID"
                                    
                                    if not text:
                                        return None, "❌ Please enter test text"
                                    
                                    try:
                                        import tempfile
                                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                                            output_path = f.name
                                        
                                        session.doubao_backend.generate_speech(
                                            text=text,
                                            voice_id=speaker_id,
                                            output_path=output_path,
                                            speed=speed,
                                            volume=volume
                                        )
                                        
                                        return output_path, f"✅ Test audio generated using voice '{speaker_id}'"
                                        
                                    except Exception as e:
                                        return None, f"❌ Error: {str(e)}"
                                
                                test_btn.click(
                                    fn=test_cloned_voice,
                                    inputs=[test_speaker_id, test_text, test_speed, test_volume],
                                    outputs=[test_audio_output, test_status]
                                )
                
                gr.Markdown("---")
                gr.Markdown("""
                ### 💡 Voice Cloning Tips
                
                **Audio Quality:**
                - Use 5-20 seconds of clear speech
                - Record in a quiet environment
                - Avoid background noise and echo
                - Speak naturally at normal pace
                
                **Model Selection:**
                - **ICL 2.0**: Best overall quality, fastest training (Recommended)
                - **ICL 1.0**: Good quality, stable
                - **DiT Standard**: Focus on timbre only
                - **DiT Restoration**: Timbre + speaking style (accent, pace)
                
                **Training:**
                - Each voice can be trained up to 10 times
                - Training takes 10-30 seconds
                - You can test before activating
                - Activation is permanent!
                """)
            
            
            # ===== Tab 4: Batch Processing =====
            with gr.TabItem("📚 Batch"):
                
                gr.Markdown("""
                ### 📚 Batch Processing
                
                Process multiple novels at once. Perfect for book series or library conversion.
                """)
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Batch Settings")
                        
                        batch_voice_input = gr.Textbox(
                            label="Voice to Use",
                            value="default",
                            placeholder="Voice name or 'default'"
                        )
                        
                        batch_use_chars = gr.Checkbox(
                            label="Use Character Voices",
                            value=False,
                            info="Apply character voice attribution to all files"
                        )
                        
                        batch_btn = gr.Button("🚀 Start Batch Processing", variant="primary", size="lg")
                        
                        batch_status = gr.Textbox(
                            label="Batch Status",
                            interactive=False
                        )
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### Upload Files")
                        
                        batch_files = gr.File(
                            label="Upload Multiple Novels",
                            file_types=[".txt", ".epub", ".pdf"],
                            multiple=True
                        )
                        
                        batch_results = gr.Dataframe(
                            headers=["File", "Status", "Output", "Error"],
                            label="Batch Results",
                            interactive=False
                        )
                        
                        batch_btn.click(
                            fn=batch_generate_ui,
                            inputs=[batch_files, batch_voice_input, batch_use_chars],
                            outputs=[batch_results, batch_status]
                        )
            
            
            # ===== Tab 5: Advanced Settings =====
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
            Novel Audiobook Generator v1.2.3 | 
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
