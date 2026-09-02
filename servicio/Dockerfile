FROM node:22-alpine
WORKDIR /servicio
COPY package.json ./
RUN npm install --omit=dev
COPY src ./src
EXPOSE 3000
CMD ["node", "src/index.js"]
