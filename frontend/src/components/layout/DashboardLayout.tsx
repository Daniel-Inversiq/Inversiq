import { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { Overview } from '../../pages/Overview';
import { Offertes } from '../../pages/Offertes';
import { Klussen } from '../../pages/Klussen';
import { Review } from '../../pages/Review';
import { Agenda } from '../../pages/Agenda';
import { Abonnement } from '../../pages/Abonnement';
import { Instellingen } from '../../pages/Instellingen';
import { Intake } from '../../pages/Intake';

const pageTitles: Record<string, string> = {
  overzicht: 'Overzicht',
  offertes: 'Offertes',
  klussen: 'Klussen',
  review: 'Review',
  agenda: 'Agenda',
  abonnement: 'Abonnement',
  instellingen: 'Instellingen',
  intake: 'Nieuwe intake',
};

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
      <p className="text-sm font-semibold text-slate-400 dark:text-slate-500">{title}</p>
      <p className="text-xs text-slate-400 dark:text-slate-600 mt-1">Deze pagina is nog niet beschikbaar</p>
    </div>
  );
}

export function DashboardLayout() {
  const [activeItem, setActiveItem] = useState('overzicht');
  const title = pageTitles[activeItem] ?? activeItem;

  const renderPage = () => {
    switch (activeItem) {
      case 'overzicht': return <Overview onNavigate={setActiveItem} />;
      case 'offertes': return <Offertes />;
      case 'klussen': return <Klussen />;
      case 'review': return <Review onNavigate={setActiveItem} />;
      case 'agenda': return <Agenda />;
      case 'abonnement': return <Abonnement />;
      case 'instellingen': return <Instellingen onNavigate={setActiveItem} />;
      case 'intake': return <Intake onNavigate={setActiveItem} />;
      default: return <PlaceholderPage title={title} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f5] dark:bg-[#0d1117]">
      <Sidebar activeItem={activeItem} onNavigate={setActiveItem} />
      <div className="pl-52">
        <Header title={title} breadcrumb="Inversiq" />
        <main className="px-6 py-6 sm:px-8 sm:py-7">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
