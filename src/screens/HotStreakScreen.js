import React, {useState} from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';

const SAMPLE_HOT_STREAK = [
  {
    id: '1',
    name: 'Player A',
    improvement: '+5 positions',
    tournaments: 3,
    trend: 'up',
  },
  {
    id: '2',
    name: 'Player B',
    improvement: '+3 positions',
    tournaments: 4,
    trend: 'up',
  },
  {
    id: '3',
    name: 'Player C',
    improvement: '+7 positions',
    tournaments: 2,
    trend: 'up',
  },
];

export default function HotStreakScreen() {
  const [hotStreakPlayers, setHotStreakPlayers] = useState(SAMPLE_HOT_STREAK);

  const renderPlayerItem = ({item}) => (
    <View style={styles.playerItem}>
      <View style={styles.playerInfo}>
        <Text style={styles.playerName}>{item.name}</Text>
        <Text style={styles.improvement}>
          {item.trend === 'up' ? '📈' : '📉'} {item.improvement}
        </Text>
        <Text style={styles.tournaments}>
          Over {item.tournaments} tournaments
        </Text>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>🔥 Hot Streak</Text>
        <Text style={styles.subtitle}>
          Players on the rise with improving tournament placements
        </Text>
      </View>

      <FlatList
        data={hotStreakPlayers}
        renderItem={renderPlayerItem}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContainer}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No players on hot streak</Text>
            <Text style={styles.emptyHint}>
              Check back after more tournaments complete
            </Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  header: {
    padding: 24,
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#f1f5f9',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#94a3b8',
    textAlign: 'center',
  },
  listContainer: {
    padding: 16,
  },
  playerItem: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  playerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  playerName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#f1f5f9',
    flex: 1,
  },
  improvement: {
    fontSize: 16,
    color: '#10b981',
    fontWeight: '500',
    marginRight: 12,
  },
  tournaments: {
    fontSize: 14,
    color: '#94a3b8',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyText: {
    fontSize: 18,
    color: '#94a3b8',
    textAlign: 'center',
    marginBottom: 8,
  },
  emptyHint: {
    fontSize: 14,
    color: '#64748b',
    textAlign: 'center',
  },
});