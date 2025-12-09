# Stock Busters - AI-Powered Investment Platform Frontend

A modern, AI-powered stock trading assistant built with Next.js 15, featuring real-time chat interactions, personalized stock recommendations, and comprehensive analytics with quantamental scoring models.

## 🚀 Features

### Chat Interface
- **Real-time AI Chat**: Interactive conversations with an AI trading assistant
- **Chat History**: Browse and continue previous conversations
- **Contextual Responses**: AI analyzes your questions and provides personalized stock recommendations
- **Report Generation**: Generate comprehensive stock reports from chat conversations

### Stock Reports
- **AI-Driven Recommendations**: View curated stock recommendations with AI rankings
- **Multiple Scoring Models**: Technical, Fundamental, and Hybrid AI scores
- **Sortable Data Tables**: Sort stocks by symbol, sector, signal, scores, Sharpe ratio, CAGR, and max drawdown
- **Pagination**: Flexible results per page (5, 10, 25, 50, 100)
- **Report History**: Access and review previously generated reports
- **Color-Coded Signals**: Visual indicators for Buy, Sell, and Hold recommendations

### Stock Detail Pages
- **Candlestick Charts**: Professional stock price visualization with OHLC data
- **Volume Analysis**: Trading volume charts with historical comparisons
- **Time Range Selection**: View data across multiple timeframes (1W, 1M, 3M, 6M, 1Y, YTD, 5Y, MAX)
- **AI Analysis**: Detailed bullet-point explanations for stock recommendations
- **Company Information**: Comprehensive company details, metrics, and descriptions
- **Key Metrics Dashboard**: AI scores (Technical/Fundamental/Hybrid), Sharpe ratio, CAGR, and Max Drawdown
- **Market News**: Latest news articles related to the stock

### Settings & Profile Management
- **Investment Profile**: Customize your investment preferences
- **Risk Tolerance**: Set your risk tolerance level
- **Investment Goals**: Define your investment objectives
- **Preferred Sectors**: Select your preferred market sectors
- **Time Horizon**: Specify your investment time horizon
- **Model Selection**: Choose between Technical, Fundamental, or Hybrid AI scoring models

## 🛠️ Tech Stack

- **Framework**: Next.js 15.5.6 (App Router)
- **Language**: JavaScript/React
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **Charts**: Recharts
- **Authentication**: NextAuth.js
- **Markdown**: react-markdown with remark-gfm and rehype-raw
- **Backend Integration**: FastAPI with Docker
- **Data Storage**: Google Cloud Storage (for quantamental models)
- **Docker Network**: Custom Docker network for container communication

## 📋 Prerequisites

- Node.js 18.x or higher
- npm or yarn
- Docker (for running api-service container)
- Backend API service running in Docker on port 9000

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment variables**
   
   The `.env.development` file is already configured with:
   ```env
   REACT_APP_BASE_API_URL=http://localhost:9000
   CHOKIDAR_USEPOLLING=true
   PORT=3000
   NEXT_PUBLIC_BASE_API_URL=http://localhost:9000
   NEXTAUTH_SECRET="gHDgDM7d7hcKJWMwqvYzH/6gEZ8gM4Yv5V76Qc/9d/s="
   NEXTAUTH_URL=http://localhost:3000
   ```

## 🚦 Running the Application

### Development Mode with Docker

The application uses Docker containers connected through a custom network:

1. **Start the API service container**
   
   Navigate to the backend directory and run:
   ```bash
   ./docker-shell.sh
   ```
   
   This creates a Docker network named `stockbusters-app-network` and starts the api-service container.

2. **Start the frontend development server**
   
   In the frontend directory:
   ```bash
   npm run dev
   ```
   
   The frontend runs on port 3000 and communicates with the API service on port 9000.

3. **Open your browser**
   
   Navigate to [http://localhost:3000](http://localhost:3000)

### Production Mode

1. **Build the application**
   ```bash
   npm run build
   ```

2. **Start the production server**
   ```bash
   npm start
   ```

## 📁 Project Structure

```
frontend/
├── app/
│   ├── about/
│   │   └── AboutSection.jsx       # About page section
│   ├── chat/
│   │   ├── page.jsx                # Main chat page
│   │   ├── ChatHistory.jsx         # Chat history component
│   │   ├── ChatHistorySidebar.jsx  # Chat sidebar navigation
│   │   ├── ChatInput.jsx           # Message input component
│   │   └── ChatMessage.jsx         # Message display component
│   ├── layout/
│   │   ├── Footer.jsx              # Footer component
│   │   ├── Header.jsx              # Header/navigation component
│   │   └── ThemeToggle.jsx         # Theme switcher
│   ├── report/
│   │   ├── page.jsx                # Stock report page
│   │   ├── ReportSidebar.jsx       # Report history sidebar
│   │   └── ReportTable.jsx         # Stock recommendations table
│   ├── settings/
│   │   ├── page.jsx                # Settings main page
│   │   ├── CheckboxGroup.jsx       # Checkbox group component
│   │   ├── FormField.jsx           # Form field component
│   │   ├── ProfileHeader.jsx       # Profile header
│   │   ├── SelectField.jsx         # Select dropdown component
│   │   ├── SettingsItem.jsx        # Individual setting item
│   │   ├── SettingsSection.jsx     # Settings section wrapper
│   │   └── ToggleSwitch.jsx        # Toggle switch component
│   ├── stock/
│   │   ├── page.jsx                # Stock detail page
│   │   ├── StockPriceChart.jsx     # Candlestick price chart
│   │   └── StockVolumeChart.jsx    # Volume bar chart
│   ├── ui/
│   │   └── MarketNewsCard.jsx      # Market news card component
│   ├── globals.css                 # Global styles
│   ├── layout.jsx                  # Root layout
│   ├── not-found.jsx               # 404 page
│   └── page.jsx                    # Home page
├── components/
│   └── ui/                         # shadcn/ui components
│       ├── alert.jsx
│       ├── avatar.jsx
│       ├── badge.jsx
│       ├── button.jsx
│       ├── card.jsx
│       ├── checkbox.jsx
│       ├── dialog.jsx
│       ├── dropdown-menu.jsx
│       ├── input.jsx
│       ├── label.jsx
│       ├── select.jsx
│       ├── separator.jsx
│       ├── switch.jsx
│       ├── table.jsx
│       ├── tabs.jsx
│       └── textarea.jsx
├── hooks/
│   └── [custom hooks]
├── lib/
│   ├── Common.js                   # Utility functions
│   ├── DataService.js              # API service layer
│   └── utils.js                    # Helper utilities
├── .env.development                # Development environment
├── .env.production                 # Production environment
├── .gitignore
├── components.json                 # shadcn/ui config
├── docker-shell.sh                 # Docker helper script
├── Dockerfile                      # Docker configuration
├── Dockerfile.dev                  # Development Docker config
├── jsconfig.json                   # JavaScript config
├── next.config.js                  # Next.js configuration
├── package-lock.json
├── package.json
├── postcss.config.js               # PostCSS configuration
├── README.md
└── tailwind.config.js              # Tailwind CSS configuration
```

## 🔌 API Integration

### Backend Endpoints

The frontend integrates with a FastAPI backend running in Docker on port 9000:

#### Chat Operations
```
GET    http://localhost:9000/api/chats?model={model}&limit={limit}
GET    http://localhost:9000/api/chat/{chatId}?model={model}
POST   http://localhost:9000/api/chat/start?model={model}
POST   http://localhost:9000/api/chat/{chatId}/continue?model={model}
```

#### Report Operations
```
GET    http://localhost:9000/api/reports?model={model}&limit={limit}
GET    http://localhost:9000/api/report/{reportId}?model={model}
POST   http://localhost:9000/api/report/generate?model={model}
```

#### Stock Operations
```
GET    http://localhost:9000/api/stock/{symbol}?model={model}&report_id={reportId}
GET    http://localhost:9000/api/stock/{symbol}/news
```

#### Settings Operations
```
GET    http://localhost:9000/api/settings
PUT    http://localhost:9000/api/settings
```

See `lib/DataService.js` for detailed request/response formats.

### Session Management

The application uses session-based authentication with X-Session-ID headers for tracking user sessions and preferences.

## 🎨 Features Walkthrough

### 1. Set Your Investment Profile

- Navigate to Settings
- Configure your investment preferences:
  - Risk tolerance (Conservative, Moderate, Aggressive)
  - Investment goals (Growth, Income, Balanced, Preservation)
  - Preferred sectors
  - Time horizon (Short, Medium, Long term)
  - AI Model (Technical, Fundamental, Hybrid)

### 2. Chat with AI Assistant

- Start a conversation about stocks
- Ask questions like "What are the best tech stocks?"
- AI uses your profile preferences to provide personalized recommendations
- Continue conversations across sessions

### 3. Generate Stock Reports

- Chat with the AI until it provides recommendations
- Click the "Generate Report" button
- View comprehensive stock recommendations table
- Stocks are scored based on your selected AI model (Technical/Fundamental/Hybrid)
- Sort and filter results

### 4. Analyze Stock Details

- Click on any stock in a report to view details
- View candlestick price charts
- Analyze trading volume
- Read AI-generated analysis
- Check latest market news
- Switch between different time ranges (1W, 1M, 3M, 6M, 1Y, YTD, 5Y, MAX)

### 5. Review Past Reports

- Access report history from the sidebar
- Compare recommendations over time
- Track your investment insights

## 🎨 Customization

### Theme

The application supports light and dark themes with a toggle switch in the header.

### Color Schemes

The app uses CSS variables for theming. Edit `app/globals.css`:

```css
:root {
  --primary: your-color;
  --secondary: your-color;
  /* ... */
}
```

### Chart Colors

Edit chart colors in:
- `app/stock/StockPriceChart.jsx` - Line colors for candlesticks
- `app/stock/StockVolumeChart.jsx` - Bar colors for volume

## 📊 Data Models

### Chat Object
```javascript
{
  chat_id: string,
  title: string,
  dts: ISO datetime,
  messages: [
    {
      message_id: string,
      role: "user" | "assistant",
      content: string,
      timestamp: ISO datetime
    }
  ]
}
```

### Report Object
```javascript
{
  report_id: string,
  title: string,
  generated_date: ISO datetime,
  chat_id: string,
  model: "technical" | "fundamental" | "hybrid",
  stocks: [
    {
      symbol: string,
      sector: string,
      signal: "Strong Buy" | "Buy" | "Hold" | "Sell",
      technical_score: number,
      fundamental_score: number,
      hybrid_score: number,
      sharpe: number,
      cagr: number,
      max_drawdown: number
    }
  ]
}
```

### Stock Detail Object
```javascript
{
  symbol: string,
  stock_name: string,
  company_name: string,
  sector: string,
  industry: string,
  market_cap: string,
  exchange: string,
  signal: string,
  technical_score: number,
  fundamental_score: number,
  hybrid_score: number,
  sharpe: number,
  cagr: number,
  max_drawdown: number,
  description: string,
  ai_analysis: string[],
  price_data: [...],
  volume_data: [...],
  news: [...]
}
```

### User Settings Object
```javascript
{
  risk_tolerance: "conservative" | "moderate" | "aggressive",
  investment_goals: string[],
  preferred_sectors: string[],
  time_horizon: "short" | "medium" | "long",
  model: "technical" | "fundamental" | "hybrid",
  notifications: boolean,
  email_updates: boolean
}
```

## 🐛 Troubleshooting

### "Failed to fetch" errors

**Problem**: Components are trying to call API but backend isn't accessible

**Solution**: 
1. Ensure api-service container is running:
   ```bash
   docker ps | grep api-service
   ```
2. Verify Docker network exists:
   ```bash
   docker network ls | grep stockbusters-app-network
   ```
3. Check that port 9000 is accessible:
   ```bash
   curl http://localhost:9000/api/health
   ```
4. Verify `.env.development` has correct API URL

### Docker network issues

**Problem**: Containers can't communicate

**Solution**:
1. Recreate the Docker network:
   ```bash
   docker network rm stockbusters-app-network
   docker network create stockbusters-app-network
   ```
2. Restart the api-service container with docker-shell.sh
3. Restart the frontend development server

### Port conflicts

**Problem**: Port 3000 or 9000 already in use

**Solution**:
1. Check what's using the ports:
   ```bash
   lsof -i :3000
   lsof -i :9000
   ```
2. Kill the process or change ports in `.env.development`

### Charts not displaying

**Problem**: Recharts not installed or data format issue

**Solution**: 
```bash
npm install recharts
```

### Styling issues

**Problem**: Tailwind classes not applying

**Solution**: 
1. Check `tailwind.config.js` is configured
2. Ensure CSS is imported in layout
3. Verify shadcn/ui components are installed
4. Clear `.next` cache and rebuild:
   ```bash
   rm -rf .next
   npm run dev
   ```

### CORS errors

**Problem**: Cross-Origin Resource Sharing blocked

**Solution**: 
1. Verify backend CORS configuration allows `http://localhost:3000`
2. Check that X-Session-ID headers are being sent correctly
3. Ensure credentials are included in requests if needed
4. Check api-service logs for CORS-related errors

### Environment variables not loading

**Problem**: `.env.development` changes not taking effect

**Solution**:
1. Restart the development server
2. Check file name is exactly `.env.development`
3. Verify variables start with `NEXT_PUBLIC_` for client-side access
4. Clear browser cache

## 🚀 Deployment

### Docker Network Architecture

The application uses a custom Docker network for container communication:

**Network Name**: `stockbusters-app-network`

**Architecture**:
```
┌─────────────────────────────────────────┐
│     Docker Network                      │
│     stockbusters-app-network            │
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │              │    │              │  │
│  │ api-service  │◄───┤   frontend   │  │
│  │ (Port 9000)  │    │ (Port 3000)  │  │
│  │              │    │              │  │
│  └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────┘
```

### Local Development

1. **Start API Service**:
   ```bash
   cd backend
   ./docker-shell.sh
   ```
   This script:
   - Creates the `stockbusters-app-network` Docker network
   - Builds and runs the api-service container
   - Exposes port 9000 for API access

2. **Start Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```
   Frontend runs on port 3000 and connects to API on port 9000

### Vercel (Frontend Only)

1. Push code to GitHub
2. Import project in Vercel
3. Add environment variables:
   - `NEXT_PUBLIC_BASE_API_URL` (your production API URL)
   - `NEXTAUTH_SECRET`
   - `NEXTAUTH_URL`
4. Deploy

### Production Docker Deployment

**Build and Run Frontend:**
```bash
docker build -t stock-busters-frontend .
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_BASE_API_URL=http://api-service:9000 \
  --network stockbusters-app-network \
  stock-busters-frontend
```

**Note**: Ensure the api-service container is running on the same Docker network.

## 📝 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `NEXT_PUBLIC_BASE_API_URL` | Backend API base URL | `http://localhost:9000` | Yes |
| `REACT_APP_BASE_API_URL` | Legacy React API base URL | `http://localhost:9000` | Yes |
| `PORT` | Frontend port | `3000` | No |
| `CHOKIDAR_USEPOLLING` | Enable file watching in Docker | `true` | No |
| `NEXTAUTH_SECRET` | NextAuth.js secret key | - | Yes |
| `NEXTAUTH_URL` | NextAuth.js callback URL | `http://localhost:3000` | Yes |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

[Your License Here]

## 👥 Authors

Mahmood - Full Stack Developer

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Email: [your-email]
- Documentation: [your-docs-url]

## 🗺️ Roadmap

- [x] User profile and settings management
- [x] Multiple AI scoring models (Technical, Fundamental, Hybrid)
- [x] Market news integration
- [x] Theme toggle (Light/Dark mode)
- [ ] Real-time price updates via WebSocket
- [ ] Portfolio tracking and performance monitoring
- [ ] Advanced technical indicators overlay
- [ ] Export reports to PDF
- [ ] Email notifications for stock alerts
- [ ] Multi-language support
- [ ] Mobile app version (React Native)
- [ ] Social sharing features
- [ ] Watchlist management

## 🏗️ Architecture

The frontend follows a modular architecture with Docker-based backend communication:

### Frontend Architecture
- **App Router**: Next.js 15 App Router for file-based routing
- **Component Library**: Reusable UI components with shadcn/ui
- **Service Layer**: Abstracted API calls through DataService
- **State Management**: React hooks and context
- **Styling**: Tailwind CSS with custom design system
- **Type Safety**: JSDoc comments for better IDE support

### Docker Network Communication
- **Custom Network**: `stockbusters-app-network` enables container-to-container communication
- **API Service**: FastAPI backend runs in Docker container on port 9000
- **Frontend**: Next.js app communicates with API via `http://localhost:9000`
- **Session Management**: X-Session-ID headers maintain user sessions across requests
- **Environment-based Configuration**: Different settings for development and production

### Data Flow
```
User Browser (Port 3000)
    ↓
Next.js Frontend
    ↓ HTTP Requests
Docker Network (stockbusters-app-network)
    ↓
API Service Container (Port 9000)
    ↓
FastAPI Backend
    ↓
Google Cloud Storage (Quantamental Models)
```

## 📈 Performance

- **Code Splitting**: Automatic route-based code splitting
- **Image Optimization**: Next.js Image component
- **Lazy Loading**: Dynamic imports for heavy components
- **Caching**: API response caching for improved performance

---

Built with ❤️ using Next.js, React, and AI

**Stock Busters** - *Invest smarter, not harder*
