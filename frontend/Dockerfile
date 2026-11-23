# Dev image (Vite dev server with API proxy). A production nginx build comes with the deployment phase.
FROM node:24-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]
