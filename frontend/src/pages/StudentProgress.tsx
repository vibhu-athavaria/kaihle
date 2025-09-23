import React from 'react';

export const StudentProgress: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <main className="flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-gray-900 dark:text-white">My Progress</h1>
          </div>

          <div className="mb-12">
            <h2 className="mb-4 text-2xl font-bold text-gray-900 dark:text-white">Weekly Progress</h2>
            <div className="rounded-xl bg-white dark:bg-background-dark/50 p-6 shadow-sm">
              <div className="flex flex-col gap-8 md:flex-row md:items-start md:gap-12">
                <div className="flex flex-col gap-2">
                  <p className="text-base font-medium text-gray-500 dark:text-gray-400">Weekly Points</p>
                  <p className="text-5xl font-bold text-gray-900 dark:text-white">1,200</p>
                  <div className="flex items-center gap-2">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Last 7 Days</p>
                    <p className="flex items-center text-sm font-medium text-green-500">
                      <span className="material-symbols-outlined text-base">arrow_upward</span>+15%
                    </p>
                  </div>
                </div>
                <div className="min-h-[200px] flex-1">
                  <svg
                    fill="none"
                    height="100%"
                    preserveAspectRatio="xMidYMax meet"
                    viewBox="0 0 472 150"
                    width="100%"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M0 109C18.1538 109 18.1538 21 36.3077 21C54.4615 21 54.4615 41 72.6154 41C90.7692 41 90.7692 93 108.923 93C127.077 93 127.077 33 145.231 33C163.385 33 163.385 101 181.538 101C199.692 101 199.692 61 217.846 61C236 61 236 45 254.154 45C272.308 45 272.308 121 290.462 121C308.615 121 308.615 149 326.769 149C344.923 149 344.923 1 363.077 1C381.231 1 381.231 81 399.385 81C417.538 81 417.538 129 435.692 129C453.846 129 453.846 25 472 25V149H0V109Z"
                      fill="url(#paint0_linear_1131_5935)"
                    ></path>
                    <path
                      d="M0 109C18.1538 109 18.1538 21 36.3077 21C54.4615 21 54.4615 41 72.6154 41C90.7692 41 90.7692 93 108.923 93C127.077 93 127.077 33 145.231 33C163.385 33 163.385 101 181.538 101C199.692 101 199.692 61 217.846 61C236 61 236 45 254.154 45C272.308 45 272.308 121 290.462 121C308.615 121 308.615 149 326.769 149C344.923 149 344.923 1 363.077 1C381.231 1 381.231 81 399.385 81C417.538 81 417.538 129 435.692 129C453.846 129 453.846 25 472 25"
                      stroke="#0da6f2"
                      strokeLinecap="round"
                      strokeWidth="3"
                    ></path>
                    <defs>
                      <linearGradient
                        gradientUnits="userSpaceOnUse"
                        id="paint0_linear_1131_5935"
                        x1="236"
                        x2="236"
                        y1="1"
                        y2="149"
                      >
                        <stop stopColor="#0da6f2" stopOpacity="0.2"></stop>
                        <stop offset="1" stopColor="#0da6f2" stopOpacity="0"></stop>
                      </linearGradient>
                    </defs>
                  </svg>
                  <div className="mt-2 flex justify-around">
                    <p className="text-xs font-bold uppercase text-gray-400 dark:text-gray-500">Mon</p>
                    <p className="text-xs font-bold uppercase text-gray-400 dark:text-gray-500">Tue</p>
                    <p className="text-xs font-bold uppercase text-gray-400 dark:text-gray-500">Wed</p>
                    <p className="text-xs font-bold uppercase text-gray-400 dark:text-gray-500">Thu</p>
                    <p className="text-xs font-bold uppercase text-gray-400 dark:text-gray-500">Fri</p>
                    <p className="text-xs font-bold uppercase text-gray-400 dark:text-gray-500">Sat</p>
                    <p className="text-xs font-bold uppercase text-gray-400 dark:text-gray-500">Sun</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mb-12">
            <h2 className="mb-4 text-2xl font-bold text-gray-900 dark:text-white">Streaks</h2>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <div className="flex items-center gap-6 rounded-xl bg-white dark:bg-background-dark/50 p-6 shadow-sm">
                <span className="material-symbols-outlined text-5xl text-primary">local_fire_department</span>
                <div>
                  <p className="text-base font-medium text-gray-500 dark:text-gray-400">Current Streak</p>
                  <p className="text-3xl font-bold text-gray-900 dark:text-white">5 Days</p>
                </div>
              </div>
              <div className="flex items-center gap-6 rounded-xl bg-white dark:bg-background-dark/50 p-6 shadow-sm">
                <span className="material-symbols-outlined text-5xl text-primary">star</span>
                <div>
                  <p className="text-base font-medium text-gray-500 dark:text-gray-400">Longest Streak</p>
                  <p className="text-3xl font-bold text-gray-900 dark:text-white">21 Days</p>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h2 className="mb-4 text-2xl font-bold text-gray-900 dark:text-white">Badges</h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
              <div
                className="aspect-square w-full rounded-xl bg-cover bg-center"
                style={{
                  backgroundImage: `url("https://lh3.googleusercontent.com/aida-public/AB6AXuAnGN2wsG3Gh08qL7iMP66zVkGPhlJzTf40wtveICSd3gQ9j8yBXYNl2kzIFJbGEAm8BGSk-i6CngVxxxblg3GKHSLFGiD7XLB7viaWJ2LxUKPLRRFb5q2NKzwFaYnVlIM6FZ938wOpmO0CNVwvvVMGGDeROgHwj8eiXt7bSZfAJShMntaJ_d9Gp572nlkOPhh2xilRfWaOJ0PgEz6Jl5sdlUe8LyPJ6apdX_DwShprIF5z5Me3PBhc7BcfXwTrSkTX__3s5KCHPqqT")`,
                }}
              ></div>
              {/* Add other badges here */}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};