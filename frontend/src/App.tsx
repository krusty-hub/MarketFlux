import React from 'react'

function App() {
  return (
    <div className="min-h-screen bg-void-black text-sage-60 selection:bg-lime-pulse/20">
      
      {/* Navigation */}
      <nav className="fixed top-0 left-0 w-full z-50 bg-carbon-veil/80 backdrop-blur-[10px] border-b border-phosphor-blue-black">
        <div className="max-w-[1280px] mx-auto h-[64px] px-[24px] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-sm bg-lime-pulse shadow-[0_0_15px_rgba(127,238,100,0.4)]"></div>
            <span className="font-goga font-medium text-[20px] text-phosphor-white tracking-[-0.017em]">MarketFlux</span>
          </div>
          <div className="flex items-center gap-[32px] text-sm font-medium">
            <a href="#" className="text-phosphor-white hover:text-lime-pulse transition-colors">Dashboard</a>
            <a href="#" className="text-phosphor-white hover:text-lime-pulse transition-colors">Signals</a>
            <a href="#" className="text-phosphor-white hover:text-lime-pulse transition-colors">Performance</a>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-circuit-border">
              <div className="w-2 h-2 rounded-full bg-lime-pulse animate-pulse"></div>
              <span className="text-caption font-medium uppercase tracking-[0.6px] text-moss-70">Live</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="pt-[100px] pb-[80px] max-w-[1280px] mx-auto px-[24px]">
        
        {/* Hero Section */}
        <div className="py-[80px] text-center flex flex-col items-center">
          <h1 className="font-goga text-display font-medium leading-none tracking-display mb-6">
            <span className="text-lime-pulse">Institutional grade</span>
            <br />
            <span className="text-phosphor-white">AI forecasting</span>
          </h1>
          <p className="max-w-[640px] text-subheading text-moss-80 mb-10">
            MarketFlux connects to live data feeds, identifies SMC liquidity conditions, and executes probabilistic forecasts across Crypto and Forex.
          </p>
          
          <div className="flex items-center gap-3">
            <button className="bg-lime-pulse text-ground-iron px-6 py-3.5 rounded-pills font-medium hover:brightness-110 transition-all">
              Run Forecast
            </button>
            <button className="bg-transparent border border-phosphor-white text-phosphor-white px-8 py-3.5 rounded-buttons font-medium hover:bg-carbon-veil transition-all">
              View History
            </button>
          </div>
        </div>

        <hr className="border-t border-phosphor-blue-black my-[40px]" />

        {/* Dashboard Grid */}
        <div>
          <span className="block text-caption font-medium uppercase tracking-[0.6px] text-moss-70 mb-3">
            Market Intelligence
          </span>
          <h2 className="font-goga text-heading-lg font-medium text-phosphor-white tracking-heading-lg mb-8">
            Latest Signals
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-[20px]">
            {/* Example Card 1 */}
            <div className="bg-carbon-veil rounded-cards p-[32px] border border-circuit-border">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-goga text-heading-sm font-medium text-phosphor-white">BTC / USDT</h3>
                <span className="bg-lime-pulse/10 text-lime-pulse px-3 py-1 rounded-pills text-caption font-medium">5m</span>
              </div>
              <div className="mb-6">
                <div className="text-display font-medium text-lime-pulse font-goga leading-none">BUY</div>
                <div className="text-body-sm text-sage-60 mt-2">72% Model Confidence</div>
              </div>
              
              <div className="space-y-3 pt-4 border-t border-phosphor-blue-black">
                <div className="flex justify-between text-sm">
                  <span className="text-sage-40">Entry</span>
                  <span className="text-phosphor-white font-mono">103,500.0</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-sage-40">Target (2R)</span>
                  <span className="text-lime-pulse font-mono">106,000.0</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-sage-40">Stop Loss</span>
                  <span className="text-[#ff6b6b] font-mono">101,500.0</span>
                </div>
              </div>
            </div>

            {/* Example Code Window Card */}
            <div className="bg-ground-iron rounded-xl p-[24px] border border-circuit-border md:col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2.5 h-2.5 rounded-full bg-[#485346]"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-[#485346]"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-[#485346]"></div>
                <span className="ml-auto text-caption font-medium text-moss-70">signal_context.json</span>
              </div>
              <pre className="font-mono text-sm leading-[1.6] overflow-x-auto text-phosphor-white">
<span className="text-sage-60">{`{`}</span>{`
  `}
<span className="text-sage-60">"pair"</span>{`: `}<span className="text-lime-pulse">"BTC/USDT"</span>{`,
  `}
<span className="text-sage-60">"regime"</span>{`: `}<span className="text-lime-pulse">"TRENDING"</span>{`,
  `}
<span className="text-sage-60">"smc_flags"</span>{`: {
    `}
<span className="text-sage-60">"liquidity_sweep"</span>{`: `}<span className="text-[#aed2a4]">true</span>{`,
    `}
<span className="text-sage-60">"fvg"</span>{`: `}<span className="text-[#aed2a4]">true</span>{`,
    `}
<span className="text-sage-60">"choch"</span>{`: `}<span className="text-[#aed2a4]">false</span>{`
  },
  `}
<span className="text-sage-60">"session"</span>{`: `}<span className="text-lime-pulse">"LONDON"</span>{`
`}
<span className="text-sage-60">{`}`}</span>
              </pre>
            </div>
          </div>
        </div>

      </main>
    </div>
  )
}

export default App
