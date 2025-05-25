import streamlit as st
import requests
import base64
import os
import io
import time
from PIL import Image
from groq import Groq
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="AI Image Generator",
    page_icon="🎨",
    layout="wide"
)

# Initialize session state variables
if 'generated_images' not in st.session_state:
    st.session_state.generated_images = []
if 'prompt_history' not in st.session_state:
    st.session_state.prompt_history = []
if 'current_image' not in st.session_state:
    st.session_state.current_image = None

# Styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-align: center;
        background: linear-gradient(90deg, #ff6b6b, #6b47ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-header {
        font-size: 1.3rem;
        margin-bottom: 2rem;
        text-align: center;
        color: #666;
    }
    .image-container {
        display: flex;
        justify-content: center;
        margin: 1.5rem 0;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border-radius: 10px;
        padding: 1rem;
        background-color: #f8f9fa;
    }
    .stButton button {
        border-radius: 20px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .history-item {
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .history-item:hover {
        background-color: #f0f2f6;
    }
    .footer {
        text-align: center;
        color: #888;
        font-size: 0.8rem;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #eee;
    }
    .gallery-image {
        transition: transform 0.3s ease;
        cursor: pointer;
    }
    .gallery-image:hover {
        transform: scale(1.03);
    }
    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background-color: #6b47ff;
    }
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 4px 4px 0px 0px;
        padding: 10px 20px;
        background-color: #f0f2f6;
    }
    .stTabs [aria-selected="true"] {
        background-color: #6b47ff !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# App header
st.markdown("<h1 class='main-header'>AI Image Creator</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Transform your ideas into stunning visuals with AI</p>", unsafe_allow_html=True)

# Sidebar for API configuration and history
with st.sidebar:
    st.header("🔑 API Configuration")
    
    # API keys input with improved UX
    groq_api_key = st.text_input("Groq API Key", type="password", 
                                 value=os.getenv("GROQ_API_KEY", ""), 
                                 help="Enter your Groq API key")
    
    stability_api_key = st.text_input("Stability API Key", type="password", 
                                      value=os.getenv("STABILITY_API_KEY", ""), 
                                      help="Enter your Stability API key")
    
    st.divider()
    
    # Advanced settings in an expander
    with st.expander("⚙️ Advanced Settings"):
        # Model selection
        selected_model = st.selectbox(
            "LLM Model",
            ["claude-3-5-sonnet-20240229", "claude-3-opus-20240229", "llama3-70b-8192"],
            index=0,
            help="Select the Groq LLM model to use for prompt enhancement"
        )
        
        # Image generation settings
        st.subheader("Image Settings")
        img_width = st.select_slider("Width", options=[512, 768, 1024], value=1024)
        img_height = st.select_slider("Height", options=[512, 768, 1024], value=1024)
        cfg_scale = st.slider("CFG Scale", min_value=1, max_value=20, value=7,
                             help="How strictly the model follows your prompt. Higher values = more faithful to prompt")
        steps = st.slider("Steps", min_value=20, max_value=50, value=30,
                         help="Number of diffusion steps. Higher values = more detailed images but slower generation")
    
    st.divider()
    
    # History section
    st.header("📜 Prompt History")
    if st.session_state.prompt_history:
        for i, (prompt, enhanced) in enumerate(st.session_state.prompt_history):
            with st.container():
                st.markdown(f"<div class='history-item'>", unsafe_allow_html=True)
                st.caption(f"Prompt {i+1}")
                if st.button(f"{prompt[:40]}..." if len(prompt) > 40 else prompt, key=f"history_{i}"):
                    # Reuse this prompt
                    st.session_state.reuse_prompt = prompt
                    st.experimental_rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.write("Your prompt history will appear here")
    
    st.divider()
    st.markdown("<div class='footer'>Created with Groq & Stability AI • v1.2.0</div>", unsafe_allow_html=True)

# Main function to generate images with improved error handling and feedback
def generate_image(
    text_prompt, 
    groq_api_key, 
    stability_api_key, 
    model_name,
    enhance_prompt=True,
    width=1024,
    height=1024,
    cfg_scale=7,
    steps=30
):
    # Check if API keys are provided
    if not groq_api_key or not stability_api_key:
        st.error("⚠️ Please enter both API keys in the sidebar")
        return None
    
    try:
        enhanced_prompt = text_prompt
        
        # Step 1: Enhance the prompt with Groq LLM if requested
        if enhance_prompt:
            progress_text = "🧠 Enhancing your prompt with AI..."
            progress_bar = st.progress(0)
            st.write(progress_text)
            
            try:
                client = Groq(api_key=groq_api_key)
                
                system_prompt = """
                You are an expert at creating detailed image generation prompts.
                Convert the user's simple text into a detailed, vivid description for image generation.
                Focus on visual elements: subjects, composition, lighting, mood, colors, style, and details.
                Keep the enhanced prompt to 120 words or less.
                Return only the enhanced prompt, nothing else.
                """
                
                completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Create an enhanced image generation prompt from: {text_prompt}"}
                    ],
                    model=model_name,
                    temperature=0.7,
                    max_tokens=300
                )
                
                enhanced_prompt = completion.choices[0].message.content.strip()
                progress_bar.progress(40)
                
                # Display the enhanced prompt in a nice format
                with st.expander("✨ Enhanced Prompt", expanded=True):
                    st.write(enhanced_prompt)
                
            except Exception as e:
                st.error(f"⚠️ Error enhancing prompt: {str(e)}")
                st.warning("Continuing with your original prompt...")
                time.sleep(1)  # Let user read the message
                enhanced_prompt = text_prompt
            
        # Step 2: Generate image with Stability AI
        progress_text = "🎨 Generating your image..."
        if enhance_prompt:
            progress_bar.progress(50)
        else:
            progress_bar = st.progress(20)
            st.write(progress_text)
        
        try:
            # API endpoint for Stability AI
            url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {stability_api_key}"
            }
            
            body = {
                "text_prompts": [{"text": enhanced_prompt}],
                "cfg_scale": cfg_scale,
                "height": height,
                "width": width,
                "samples": 1,
                "steps": steps
            }
            
            response = requests.post(url, headers=headers, json=body)
            progress_bar.progress(80)
            
            if response.status_code != 200:
                st.error(f"⚠️ Stability API Error: {response.status_code}")
                st.write(response.text)
                return None
            
            # Parse the response and convert the first image to a PIL Image
            data = response.json()
            image_data = base64.b64decode(data["artifacts"][0]["base64"])
            image = Image.open(io.BytesIO(image_data))
            
            # Update progress
            progress_bar.progress(100)
            time.sleep(0.5)  # Allow user to see completed progress
            progress_bar.empty()
            
            # Add to history
            st.session_state.prompt_history.append((text_prompt, enhanced_prompt))
            if len(st.session_state.prompt_history) > 10:  # Keep only 10 most recent
                st.session_state.prompt_history.pop(0)
            
            # Add to generated images
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_data = buffered.getvalue()
            st.session_state.generated_images.append((img_data, text_prompt, enhanced_prompt))
            if len(st.session_state.generated_images) > 10:  # Keep only 10 most recent
                st.session_state.generated_images.pop(0)
            
            st.session_state.current_image = (image, img_data)
            return image
            
        except Exception as e:
            st.error(f"⚠️ Error generating image: {str(e)}")
            return None
    
    except Exception as e:
        st.error(f"⚠️ An error occurred: {str(e)}")
        return None

# Main app interface with tabs
tab1, tab2, tab3 = st.tabs(["🖼️ Create", "🎭 Gallery", "❓ Help"])

with tab1:
    st.subheader("Create Your Image")
    
    # Text input for image description
    text_prompt = st.text_area(
        "Describe the image you want to generate",
        placeholder="Example: A serene landscape with mountains at sunset, reflecting in a calm lake",
        height=100,
        key="prompt_input"
    )
    
    # Check if we're reusing a prompt from history
    if 'reuse_prompt' in st.session_state:
        text_prompt = st.session_state.reuse_prompt
        del st.session_state.reuse_prompt
    
    # Options in a cleaner layout
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        enhance_prompt = st.checkbox("✨ Enhance my prompt", value=True, 
                                   help="Use AI to improve your description for better results")
    with col2:
        negative_prompt = st.text_input("🚫 Negative prompt", 
                                      placeholder="Elements to avoid",
                                      help="Specify elements you don't want in the image")
    with col3:
        style_option = st.selectbox(
            "🎨 Style",
            ["None", "Photorealistic", "Digital Art", "Oil Painting", "Watercolor", "Anime", "Comic Book"],
            index=0,
            help="Select a general style for your image"
        )
    
    # Generate button
    generate_col1, generate_col2 = st.columns([3, 1])
    with generate_col1:
        generate_button = st.button("🚀 Generate Image", type="primary", use_container_width=True)
    with generate_col2:
        random_button = st.button("🎲 Random", use_container_width=True, 
                                help="Try a random example prompt")
    
    # Random example prompts
    random_examples = [
        "A cyberpunk cityscape at night with neon lights and flying cars",
        "A magical forest with glowing mushrooms and fairy creatures",
        "A futuristic space station orbiting a colorful nebula",
        "An underwater scene with coral reefs and exotic fish in vibrant colors",
        "A steampunk inventor's workshop with intricate brass machinery",
        "A cozy cottage in autumn with falling leaves and smoke from the chimney",
        "A dragon perched on a mountain peak overlooking a medieval kingdom",
        "An alien landscape with strange flora and multiple moons in the sky"
    ]
    
    # Handle random button
    if random_button:
        import random
        random_prompt = random.choice(random_examples)
        st.session_state.random_prompt = random_prompt
        st.experimental_rerun()
    
    # Use random prompt if selected
    if 'random_prompt' in st.session_state:
        text_prompt = st.session_state.random_prompt
        del st.session_state.random_prompt
    
    # Update prompt based on style selection
    if style_option != "None" and text_prompt:
        if not text_prompt.lower().endswith(f"in {style_option.lower()} style"):
            text_prompt = f"{text_prompt}, in {style_option.lower()} style"
    
    # Process generation
    if generate_button:
        if not text_prompt:
            st.warning("⚠️ Please enter a text description first")
        else:
            # Add negative prompt if specified
            full_prompt = text_prompt
            if negative_prompt:
                full_prompt = f"{text_prompt}. Avoid: {negative_prompt}"
            
            # Call the generate function
            generated_image = generate_image(
                full_prompt, 
                groq_api_key, 
                stability_api_key, 
                selected_model,
                enhance_prompt,
                img_width,
                img_height,
                cfg_scale,
                steps
            )
            
            # Display the generated image
            if generated_image:
                st.success("✅ Image generated successfully!")
                st.markdown("<div class='image-container'>", unsafe_allow_html=True)
                st.image(generated_image, caption="Generated Image", use_column_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Download button
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.download_button(
                        label="💾 Download Image",
                        data=st.session_state.current_image[1],
                        file_name=f"ai_image_{int(time.time())}.png",
                        mime="image/png",
                        use_container_width=True
                    )
                with col2:
                    # Social share button placeholder - would require backend integration
                    st.button("📤 Share Image", use_container_width=True, disabled=True, 
                           help="Social sharing integration coming soon!")

with tab2:
    st.subheader("Your Image Gallery")
    
    if st.session_state.generated_images:
        # Display in a grid
        cols = st.columns(3)
        for i, (img_data, prompt, enhanced) in enumerate(st.session_state.generated_images):
            with cols[i % 3]:
                image = Image.open(io.BytesIO(img_data))
                st.image(image, caption=f"{prompt[:30]}...", use_column_width=True, 
                         output_format="PNG", clamp=True)
                st.markdown("<div class='gallery-image'>", unsafe_allow_html=True)
                if st.button(f"⬇️ Download", key=f"download_{i}", use_container_width=True):
                    st.download_button(
                        label="Save Image",
                        data=img_data,
                        file_name=f"ai_image_{i}_{int(time.time())}.png",
                        mime="image/png",
                        key=f"download_button_{i}",
                        use_container_width=True
                    )
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Your generated images will appear here")
        
        # Sample gallery images
        st.subheader("Example Gallery")
        cols = st.columns(3)
        for i in range(3):
            with cols[i]:
                # Display placeholder images
                st.image(f"https://picsum.photos/seed/{i+1}/400/400", caption=f"Example {i+1}", use_column_width=True)

with tab3:
    st.subheader("How to Use This App")
    
    st.write("""
    ### Getting Started
    
    1. **Enter your API keys** in the sidebar:
       - Get a Groq API key from [Groq Cloud](https://console.groq.com/)
       - Get a Stability API key from [Stability AI](https://stability.ai/)
    
    2. **Create your image**:
       - Write a description of what you want to see
       - Enable prompt enhancement for better results
       - Click "Generate Image"
    
    3. **Download or share** your creation!
    
    ### Tips for Great Results
    
    - **Be specific** about what you want to see
    - Include details about **style, lighting, and mood**
    - Use the **negative prompt** to exclude unwanted elements
    - Experiment with different **enhancement models**
    - Adjust **advanced settings** for fine-tuned results
    
    ### FAQ
    
    **Q: Why does the same prompt give different results?**  
    A: Image generation has some randomness by design. For more consistent results, try lowering the temperature setting.
    
    **Q: How do I get more detailed images?**  
    A: Increase the "Steps" parameter in advanced settings and provide more specific prompts.
    
    **Q: Can I generate NSFW content?**  
    A: No, the API has safety filters that prevent generating inappropriate content.
    """)
    
    st.divider()
    
    # Expandable sections with more help
    with st.expander("Understanding Advanced Settings"):
        st.write("""
        - **CFG Scale**: Controls how closely the image follows your prompt. Higher values stick more closely to your prompt but may produce less creative results.
        
        - **Steps**: More steps generally produce more detailed images, but take longer to generate.
        
        - **Dimensions**: Different aspect ratios work better for different types of images:
          - 1024x1024: Square format, good for portraits or balanced compositions
          - 768x1024: Portrait orientation, good for character images
          - 1024x768: Landscape orientation, good for scenery
        """)
    
    with st.expander("API Key Instructions"):
        st.markdown("""
        ### Getting your API keys
        
        **Groq API Key:**
        1. Sign up at [Groq Cloud](https://console.groq.com/)
        2. Navigate to the API keys section
        3. Create a new API key and copy it
        
        **Stability API Key:**
        1. Sign up at [Stability AI](https://stability.ai/)
        2. Go to your account dashboard
        3. Create a new API key
        
        **Note**: Keep your API keys secure and never share them publicly.
        """)

# Footer with version info
st.markdown("""
<div style='text-align: center; color: #888; font-size: 0.8rem; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #eee;'>
    Text-to-Image Generator v1.2.0 | Powered by Groq & Stability AI<br>
    Built with Streamlit
</div>
""", unsafe_allow_html=True)