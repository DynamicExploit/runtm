import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { HomeHero, HomeFeatures, HomeCTA } from '@/components/pages/home';

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <HomeHero />
        <HomeFeatures />
        <HomeCTA />
      </main>
      <Footer />
    </div>
  );
}
