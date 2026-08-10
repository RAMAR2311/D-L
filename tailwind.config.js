/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
    "./routes/**/*.py"
  ],
  theme: {
    extend: {
      colors: {
        // Mario & Luigi Brand Design Tokens
        marioRed: {
          DEFAULT: '#ED1C24',
          hover: '#C8141B',
          dark: '#5E1214',
        },
        luigiGreen: {
          DEFAULT: '#4FBE37',
          hover: '#3DA627',
          dark: '#1E6D35',
        },
        accentBlue: {
          DEFAULT: '#99DEF9',
          hover: '#6EC4E8',
          dark: '#2E3192',
        },
        starYellow: {
          DEFAULT: '#F9D006',
          hover: '#E5BD05',
          dark: '#B08E00',
        },
        darkBorder: '#100F0D',
        neutralLight: '#F8F9FA',
        cardBg: '#FFFFFF',
      },
      fontFamily: {
        title: ['Fredoka', 'Luckiest Guy', 'cursive', 'sans-serif'],
        body: ['Poppins', 'Inter', 'sans-serif'],
      },
      boxShadow: {
        'cartoon': '3px 3px 0px #100F0D',
        'cartoon-lg': '5px 5px 0px #100F0D',
        'cartoon-sm': '2px 2px 0px #100F0D',
        'cartoon-red': '3px 3px 0px #5E1214',
        'cartoon-green': '3px 3px 0px #1E6D35',
        'cartoon-blue': '3px 3px 0px #2E3192',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.25rem',
        '3xl': '1.5rem',
      }
    },
  },
  plugins: [],
}
