import axios from 'axios';
import {API_BASE_URL} from '../config';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const rankingsApi = {
  getWPBA: async (limit = 100, offset = 0) => {
    const response = await api.get(`/api/rankings/wpba-women?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getWPA: async (limit = 100, offset = 0) => {
    const response = await api.get(`/api/rankings/wpa-women?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getWPAWomen: async (limit = 100, offset = 0) => {
    const response = await api.get(`/api/rankings/wpa-women?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getWPAMen: async (limit = 100, offset = 0) => {
    const response = await api.get(`/api/rankings/wpa-men?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getPlayer: async (playerName) => {
    const response = await api.get(`/api/rankings/player/${encodeURIComponent(playerName)}`);
    return response.data;
  },

  getLastUpdate: async () => {
    try {
      const response = await api.get('/api/rankings/last-update');
      return response.data;
    } catch (error) {
      return {wpba: null, wpa: null};
    }
  },
};