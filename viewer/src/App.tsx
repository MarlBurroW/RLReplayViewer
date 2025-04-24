import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import ReplayViewer from './pages/ReplayViewer';
import RawReplayViewer from './pages/RawReplayViewer';
import HomePage from './pages/HomePage';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background text-foreground">
        <header className="border-b border-border">
          <div className="container mx-auto py-4 px-4 flex justify-between items-center">
            <h1 className="text-xl font-bold">
              <Link to="/">RL Replay Viewer</Link>
            </h1>
            <nav>
              <ul className="flex space-x-4">
                <li>
                  <Link to="/" className="hover:text-primary transition-colors">
                    Home
                  </Link>
                </li>
              </ul>
            </nav>
          </div>
        </header>
        
        <main className="container mx-auto py-8 px-4">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/replay/:replayId" element={<ReplayViewer />} />
            <Route path="/replay/:replayId/raw" element={<RawReplayViewer />} />
          </Routes>
        </main>
        
        <footer className="border-t border-border py-6 mt-12">
          <div className="container mx-auto px-4 text-center text-muted-foreground">
            <p>RL Replay Viewer &copy; {new Date().getFullYear()}</p>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;
