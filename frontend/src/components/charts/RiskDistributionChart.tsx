import React from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from 'recharts';
import { ChartRiskPoint } from '../../types/api';
import { EmptyState } from '../common/EmptyState';
import { PieChart as PieChartIcon } from 'lucide-react';

interface RiskDistributionChartProps {
  data: ChartRiskPoint[];
  loading?: boolean;
}

export const RiskDistributionChart: React.FC<RiskDistributionChartProps> = ({
  data,
  loading = false,
}) => {
  if (loading) {
    return (
      <div className="h-72 flex items-center justify-center bg-slate-900/40 rounded-xl border border-slate-800">
        <div className="w-8 h-8 border-2 border-slate-700 border-t-emerald-500 rounded-full animate-spin" />
      </div>
    );
  }

  const totalValue = data.reduce((sum, item) => sum + item.value, 0);

  if (!data || totalValue === 0) {
    return (
      <div className="h-72 flex items-center justify-center">
        <EmptyState
          icon={<PieChartIcon className="w-6 h-6 text-slate-500" />}
          title="No transactions classified"
          description="Risk breakdown will visualize legitimate vs high-risk/fraud transactions once scored."
        />
      </div>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={4}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} stroke="#0f172a" strokeWidth={2} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              borderColor: '#334155',
              borderRadius: '0.5rem',
              color: '#f8fafc',
              fontSize: '12px',
            }}
            formatter={(value: number) => [`${value} transactions (${((value / totalValue) * 100).toFixed(1)}%)`, 'Count']}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};
