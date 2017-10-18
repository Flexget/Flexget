export default [
  {
    link: '/config',
    icon: 'pencil',
    label: 'Config',
  },
  {
    link: '/history',
    icon: 'history',
    label: 'History',
  },
  {
    link: '/log',
    icon: 'book',
    label: 'Log',
  },
  {
    link: '/movies',
    icon: 'film',
    label: 'Movies',
  },
  {
    link: '/pending',
    icon: 'check',
    label: 'Pending',
  },
  {
    link: '/seen',
    icon: 'eye',
    label: 'Seen',
  },
  {
    link: '/series',
    icon: 'tv',
    label: 'Series',
  },
  {
    icon: 'tasks',
    label: 'Tasks',
    children: [
      {
        link: '/tasks/execute',
        icon: 'cogs',
        label: 'Execute',
      },
      {
        link: '/tasks/schedule',
        icon: 'clock-o',
        label: 'Schedule',
      },
      {
        link: '/tasks/status',
        icon: 'heartbeat',
        label: 'Status',
      },
    ],
  },
];
