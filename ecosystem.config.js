// PM2 process definitions for local development.
//
//   pm2 start ecosystem.config.js      # start backend + frontend
//   pm2 status                         # see both processes
//   pm2 logs lms-backend               # tail a process
//   pm2 restart lms-backend
//   pm2 delete all                     # stop everything
//
// Postgres runs separately via `docker compose up -d db` (see docker-compose.yml).
module.exports = {
  apps: [
    {
      name: "lms-backend",
      cwd: "./backend",
      // Use the project virtualenv's Python directly.
      script: "./.venv/bin/python",
      args: "manage.py runserver 0.0.0.0:8080",
      interpreter: "none",
      env: {
        DJANGO_SETTINGS_MODULE: "config.settings.dev",
      },
      watch: false,
      autorestart: true,
    },
    {
      name: "lms-frontend",
      cwd: "./frontend",
      script: "npm",
      args: "run dev",
      interpreter: "none",
      watch: false,
      autorestart: true,
    },
  ],
};
