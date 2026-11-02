import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { ChartLocationPoint } from '../../types/api';
import { EmptyState } from '../common/EmptyState';
import { MapPin } from 'lucide-react';

interface LocationChartProps {
  data: ChartLocationPoint[];
  loading?: boolean;
}

export const LocationChart: React.FC<LocationChartProps> = ({
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

  if (!data || data.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center">
        <EmptyState
          icon={<MapPin className="w-6 h-6 text-slate-500" />}
          title="No geographic metrics"
          description="Regional volume and geographic fraud distribution will display here."
        />
      </div>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 10, right: 20, left: 20, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} horizontal={false} />
          <XAxis
            type="number"
            stroke="#94a3b8"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="location"
            stroke="#94a3b8"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            width={75}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              borderColor: '#334155',
              borderRadius: '0.5rem',
              color: '#f8fafc',
              fontSize: '12px',
            }}
          />
          <Legend
            verticalAlign="top"
            height={36}
            wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
          />
          <Bar dataKey="total" name="Total Volume" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
          <Bar dataKey="fraud" name="Fraud Detected" fill="#f43f5e" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
