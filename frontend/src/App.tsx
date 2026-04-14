import { ThemeProvider } from './contexts/ThemeContext';
import { DashboardLayout } from './components/layout/DashboardLayout';

function App() {
  return (
    <ThemeProvider>
      <DashboardLayout />
    </ThemeProvider>
  );
}

export default App;
