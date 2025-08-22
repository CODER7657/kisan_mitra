# 🌾 Kisan Mitra AI - Smart Agricultural Diagnostic Platform

[![Deployed on Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black?style=flat&logo=vercel)](https://kisan-mitra-seven.vercel.app/) [![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/) [![Svelte](https://img.shields.io/badge/Frontend-SvelteKit-FF3E00?style=flat&logo=svelte)](https://kit.svelte.dev/) [![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python)](https://python.org) [![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript)](https://www.typescriptlang.org/)

> ⚠️ **Development Status**: This project is currently in the development stage and substantial work is still in progress. Features may be incomplete or subject to change.

**Kisan Mitra AI** is an intelligent agricultural diagnostic platform that empowers farmers with AI-driven insights for crop health management, disease detection, and personalized farming recommendations. Using advanced multimodal analysis, the platform processes video, audio, and historical data to provide comprehensive agricultural guidance.

## 🚀 Live Demo

**🌐 [Visit Kisan Mitra AI](https://kisan-mitra-gilt.vercel.app/)**

## ✨ Key Features

### 🔬 **Multimodal AI Analysis**
- **Video Analysis**: Computer vision for plant disease detection and crop health assessment
- **Audio Processing**: Voice query processing using OpenAI Whisper for natural farmer interaction
- **Historical Data Integration**: Analysis of farming history and patterns for personalized recommendations

### 🤖 **AI-Powered Diagnostics**
- **Disease Identification**: Accurate detection of plant diseases, pest infestations, and nutrient deficiencies
- **Personalized Recommendations**: Tailored treatment plans based on specific farm conditions
- **Preventive Measures**: Long-term strategies to prevent recurring agricultural issues
- **Expert Guidance**: Step-by-step actionable plans for farmers

### 🎯 **User-Friendly Interface**
- **Intuitive Upload System**: Easy file submission for video, audio, and historical data
- **Real-time Analysis**: Fast processing with immediate results
- **Markdown-Formatted Reports**: Detailed, well-structured diagnostic reports
- **Multi-language Support**: Voice queries in multiple languages via Whisper

## 🏗️ Technical Architecture

### Backend (FastAPI)
```
backend/
├── main.py              # Main FastAPI application with multimodal endpoints
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (API keys, tokens)
└── __pycache__/        # Python cache files
```

### Frontend (SvelteKit)
```
frontend/
├── src/
│   ├── routes/         # SvelteKit routing and pages
│   ├── lib/            # Shared components and utilities
│   ├── app.html        # Main HTML template
│   └── app.d.ts        # TypeScript declarations
├── static/             # Static assets
├── package.json        # Node.js dependencies
├── svelte.config.js    # Svelte configuration
├── vite.config.ts      # Vite build configuration
└── tsconfig.json       # TypeScript configuration
```

## 🔧 Technology Stack

### Backend Technologies

• [FastAPI](https://fastapi.tiangolo.com/) - High-performance Python web framework
• [OpenAI GPT-4o](https://openai.com/) - Advanced language model for agricultural analysis
• [OpenAI Whisper](https://openai.com/whisper/) - Speech-to-text for audio query processing
• [Vercel Blob Storage](https://vercel.com/docs/storage/vercel-blob) - Scalable file storage for uploads
• [Python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management
• [Uvicorn](https://www.uvicorn.org/) - Lightning-fast ASGI server

### Frontend Technologies

• [SvelteKit 2.0](https://kit.svelte.dev/) - Full-stack Svelte framework
• [Svelte 5.0](https://svelte.dev/) - Reactive UI framework
• [TypeScript 5.0+](https://www.typescriptlang.org/) - Type-safe JavaScript
• [Vite 7.0](https://vitejs.dev/) - Next-generation build tool
• [Marked](https://marked.js.org/) - Markdown parser for rendering reports

### Deployment & Infrastructure

• [Vercel](https://vercel.com/) - Frontend hosting and deployment
• [Render](https://render.com/) - Backend API hosting
• CORS-enabled - Cross-origin resource sharing for seamless integration

## ⚙️ Installation & Setup

### Prerequisites

• Node.js 18+ and npm
• Python 3.8+ and pip
• OpenAI API Key
• Vercel Blob Storage Token

### Backend Setup

1. Clone the repository
```bash
git clone https://github.com/CODER7657/kisan_mitra.git
cd kisan_mitra/backend
```

2. Install Python dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment variables
```bash
# Create .env file
cp .env.example .env

# Add your API keys
OPENAI_API_KEY=your_openai_api_key_here
BLOB_READ_WRITE_TOKEN=your_vercel_blob_token_here
```

4. Run the FastAPI server
```bash
uvicorn main:app --reload
```
Server will start at http://localhost:8000

### Frontend Setup

1. Navigate to frontend directory
```bash
cd ../frontend
```

2. Install Node.js dependencies
```bash
npm install
```

3. Start the development server
```bash
npm run dev
```
Application will start at http://localhost:5173

## 📚 API Documentation

### Core Endpoints

#### GET /

Health check endpoint to verify server status.

Response:
```json
{
  "message": "Welcome to the Kisan Mitra AI Backend!"
}
```

#### POST /analyze/

Main analysis endpoint for multimodal agricultural diagnostics.

Parameters:
• video_file (File): Video of crop/plant for visual analysis
• audio_file (File): Audio query from farmer
• history_file (File): Text file with farming historical data

Response:
```json
{
  "analysis": "Detailed markdown-formatted diagnostic report",
  "video_url": "https://blob.vercel-storage.com/...",
  "audio_url": "https://blob.vercel-storage.com/...",
  "history_url": "https://blob.vercel-storage.com/...",
  "transcript": "Transcribed farmer query"
}
```

## 🚀 Deployment

### Frontend Deployment (Vercel)

1. Connect your GitHub repository to Vercel
2. Configure build settings:
   • Build Command: npm run build
   • Output Directory: build
   • Root Directory: frontend

### Backend Deployment (Render/Railway)

1. Create new web service
2. Connect repository
3. Configure environment variables
4. Deploy with Python runtime

## 🤝 Contributing

We welcome contributions from the agricultural technology community! Here's how you can help:

### Development Team

• [Pavan Patel (@CODER7657)](https://github.com/CODER7657) - Lead Developer & Project Maintainer
• [Hem Patel (@Hem60)](https://github.com/Hem60) - Backend Developer
• [Ayush (@Ayush3422)](https://github.com/Ayush3422) - Frontend Developer

### How to Contribute

1. Fork the repository
2. Create a feature branch
```bash
git checkout -b feature/amazing-feature
```

3. Commit your changes
```bash
git commit -m 'Add amazing feature'
```

4. Push to the branch
```bash
git push origin feature/amazing-feature
```

5. Open a Pull Request

### Areas for Contribution

• 🌱 Agricultural Models: Improve disease detection algorithms
• 🎨 UI/UX: Enhance user interface and experience
• 🌍 Localization: Add support for regional languages
• 📱 Mobile: Develop mobile-responsive features
• 🔬 Testing: Add comprehensive test coverage
• 📖 Documentation: Improve documentation and guides

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/CODER7657/kisan_mitra/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

• OpenAI for providing cutting-edge AI models (GPT-4o, Whisper)
• Vercel for seamless deployment and blob storage services
• FastAPI Community for the excellent web framework
• Svelte Team for the innovative frontend framework
• Agricultural Research Community for domain expertise and insights

## 📞 Support

• 🐛 Issues: [GitHub Issues](https://github.com/CODER7657/kisan_mitra/issues)
• 💬 Discussions: [GitHub Discussions](https://github.com/CODER7657/kisan_mitra/discussions)
• 📧 Email: Contact project maintainers

## 🔮 Roadmap

- [ ] Mobile App Development (React Native/Flutter)
- [ ] Offline Mode for areas with poor connectivity
- [ ] IoT Integration for sensor data analysis
- [ ] Crop Yield Prediction using historical data
- [ ] Weather API Integration for better recommendations
- [ ] Farmer Community Platform for knowledge sharing
- [ ] Multi-language Voice Support (Hindi, Telugu, Tamil, etc.)
- [ ] AR/VR Plant Scanning for enhanced diagnostics

### 🌾 Empowering Farmers with AI-Driven Agricultural Intelligence 🌾

Made with ❤️ for the farming community

[![GitHub stars](https://img.shields.io/github/stars/CODER7657/kisan_mitra)](https://github.com/CODER7657/kisan_mitra/stargazers) [![GitHub forks](https://img.shields.io/github/forks/CODER7657/kisan_mitra)](https://github.com/CODER7657/kisan_mitra/network/members) [![GitHub watchers](https://img.shields.io/github/watchers/CODER7657/kisan_mitra)](https://github.com/CODER7657/kisan_mitra/watchers)
