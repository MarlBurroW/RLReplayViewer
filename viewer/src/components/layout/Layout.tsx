import React from "react";
import { Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="min-h-screen bg-background dark text-foreground flex flex-col">
      <header className="border-b border-border py-4">
        <div className="container mx-auto px-4">
          <h1 className="text-2xl font-bold">RL Replay Viewer</h1>
        </div>
      </header>
      
      <main className="flex-1 container mx-auto px-4 py-8">
        <Outlet />
      </main>
      
      <footer className="border-t border-border py-4">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          RL Replay Viewer &copy; {new Date().getFullYear()}
        </div>
      </footer>
    </div>
  );
} 